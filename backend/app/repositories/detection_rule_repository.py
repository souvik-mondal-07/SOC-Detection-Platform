import logging
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError
from pymongo import ASCENDING, IndexModel

from app.core.database import COLLECTION_RULES
from app.models.rule import DetectionRule
from app.repositories.base import BaseRepository, translate_db_errors

logger = logging.getLogger("soc.detection")

MAX_RULES = 500  # cap for engine loads
MAX_PAGE_LIMIT = 100  # cap for one page of the management API


class DetectionRuleRepository(BaseRepository[DetectionRule]):
    model = DetectionRule
    collection_name = COLLECTION_RULES
    id_field = "rule_id"
    indexes = (
        IndexModel([("rule_id", ASCENDING)], name="uq_rule_id", unique=True),
        IndexModel([("category", ASCENDING)], name="ix_category"),  # list rules by category
        IndexModel([("enabled", ASCENDING)], name="ix_enabled"),  # engine loads enabled rules
        IndexModel([("severity", ASCENDING)], name="ix_severity"),  # filter rules by severity (Step 7)
    )

    def get_rule(self, rule_id: str) -> DetectionRule | None:
        return self.find_by_id(rule_id)

    def list_rules(self, *, category: str | None = None, enabled: bool | None = None) -> list[DetectionRule]:
        """Rules ordered by rule_id. Stored documents that fail validation are skipped, not fatal."""
        query: dict[str, Any] = {}
        if category is not None:
            query["category"] = category
        if enabled is not None:
            query["enabled"] = enabled
        return self._load_valid(self._fetch(query))

    def get_enabled_rules(self) -> list[DetectionRule]:
        """Rules the engine should evaluate. Corrupt documents are logged and skipped."""
        return self.list_rules(enabled=True)

    def save_rule(self, rule: DetectionRule) -> tuple[DetectionRule, bool]:
        """Create the rule, or update an existing one with the same rule_id (no duplicates).

        Definition fields are refreshed. The existing `enabled` flag and `created_at`
        are kept, so re-seeding never silently re-enables a rule an operator turned off.
        Returns (stored rule, created).
        """
        existing = self.find_by_id(rule.rule_id)
        if existing is None:
            return self.create(rule), True
        changes = {
            "name": rule.name,
            "category": rule.category,
            "description": rule.description,
            "severity": rule.severity,
            "conditions": rule.conditions,
        }
        updated = self.update(rule.rule_id, changes)
        if updated is None:  # deleted between the lookup and the update: just create it
            return self.create(rule), True
        return updated, False

    # -- rule management (Step 7) ----------------------------------------------------

    def create_rule(self, rule: DetectionRule) -> DetectionRule:
        """Insert a new rule. Raises DuplicateRecordError if the rule_id exists."""
        return self.create(rule)

    def get_rules(
        self,
        *,
        category: str | None = None,
        severity: str | None = None,
        enabled: bool | None = None,
        name: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[DetectionRule], int]:
        """One page of rules ordered by rule_id, plus the total number matching the filters.

        All filtering, counting, skipping and limiting happen inside MongoDB.
        `name` is a case-insensitive substring match (escaped, never a user regex).
        """
        if not 1 <= limit <= MAX_PAGE_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_LIMIT}")
        if skip < 0:
            raise ValueError("skip must be 0 or greater")
        query = self._build_query(category=category, severity=severity, enabled=enabled, name=name)
        with translate_db_errors():
            total = self._collection.count_documents(query)
            cursor = self._collection.find(query, {"_id": 0}).sort("rule_id", ASCENDING).skip(skip).limit(limit)
            documents = list(cursor)
        return self._load_valid(documents), total

    def update_rule(self, rule_id: str, changes: Mapping[str, Any]) -> DetectionRule | None:
        """Partial update; rule_id and created_at are immutable, updated_at is set here.
        Returns None if the rule does not exist. Raises ValidationError for an invalid result."""
        return self.update(rule_id, changes)

    def set_enabled(self, rule_id: str, enabled: bool) -> DetectionRule | None:
        """Enable or disable a rule. The engine reads rules on every evaluation, so this is immediate."""
        return self.update(rule_id, {"enabled": enabled})

    def delete_rule(self, rule_id: str) -> bool:
        """Delete one rule by rule_id. Returns False if it did not exist."""
        with translate_db_errors():
            result = self._collection.delete_one({"rule_id": rule_id})
        return result.deleted_count == 1

    # -- helpers ----------------------------------------------------------------

    @staticmethod
    def _build_query(*, category=None, severity=None, enabled=None, name=None) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if category is not None:
            query["category"] = category
        if severity is not None:
            query["severity"] = severity
        if enabled is not None:
            query["enabled"] = enabled
        if name:
            query["name"] = {"$regex": re.escape(name), "$options": "i"}
        return query

    def _fetch(self, query: Mapping[str, Any]) -> list[dict[str, Any]]:
        with translate_db_errors():
            cursor = self._collection.find(dict(query), {"_id": 0}).sort("rule_id", ASCENDING).limit(MAX_RULES)
            return list(cursor)

    @staticmethod
    def _load_valid(documents: Iterable[dict[str, Any]]) -> list[DetectionRule]:
        rules = []
        for document in documents:
            try:
                rules.append(DetectionRule.from_document(document))
            except ValidationError:
                # Stored rules are untrusted configuration: never crash detection over one bad document.
                logger.warning("Skipping invalid stored detection rule %r", str(document.get("rule_id"))[:40])
        return rules
