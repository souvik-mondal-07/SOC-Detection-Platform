"""Rule management: validation and business rules for detection rules.

No HTTP code here and no direct MongoDB access (everything goes through
DetectionRuleRepository). The detection engine does not use this service: it
reads enabled rules from the same repository, so MongoDB stays the single
source of truth and every change here is seen by the next evaluation.

Conditions are validated with the engine's own parser (app.detection.conditions),
so a rule that can be saved is a rule the engine can interpret. Conditions are
plain data; nothing is ever evaluated as code.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.core.errors import DuplicateRecordError, summarize_validation_errors
from app.detection.base import InvalidRuleError
from app.detection.conditions import parse_conditions
from app.models.rule import DetectionRule
from app.repositories.detection_rule_repository import MAX_PAGE_LIMIT, DetectionRuleRepository

DEFAULT_PAGE_LIMIT = 20

# The initial rules created by scripts/seed_detection_rules.py. Deleting one needs
# an explicit force flag (disable it instead). This guards against accidents; it is
# not an authorization mechanism (authentication comes in a later step).
PROTECTED_RULE_IDS = frozenset({"AUTH-001", "AUTH-002", "AUTH-003", "WEB-001", "NET-001"})


class RuleServiceError(Exception):
    """Base class. Subclasses carry a stable error_code and a client-safe message."""

    error_code = "INVALID_RULE"
    message = "Invalid detection rule"

    def __init__(self, message: str | None = None, details: list[dict[str, str]] | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details


class RuleNotFoundError(RuleServiceError):
    error_code = "RULE_NOT_FOUND"
    message = "Detection rule not found"


class RuleAlreadyExistsError(RuleServiceError):
    error_code = "RULE_ALREADY_EXISTS"
    message = "Detection rule already exists"


class RuleProtectedError(RuleServiceError):
    error_code = "RULE_PROTECTED"
    message = "This is an initial system rule. Disable it instead, or delete it with force=true"


class InvalidRuleDataError(RuleServiceError):
    error_code = "INVALID_RULE"


class InvalidConditionError(RuleServiceError):
    error_code = "INVALID_CONDITION"
    message = "Invalid rule conditions"


class InvalidSeverityError(RuleServiceError):
    error_code = "INVALID_SEVERITY"
    message = "Invalid severity. Allowed: low, medium, high, critical"


class InvalidStatusError(RuleServiceError):
    error_code = "INVALID_STATUS"
    message = "enabled must be true or false"


class InvalidCategoryError(RuleServiceError):
    error_code = "INVALID_CATEGORY"
    message = "Invalid category"


@dataclass(frozen=True)
class RulePage:
    rules: list[DetectionRule]
    total: int
    page: int
    limit: int


_FIELD_ERRORS: dict[str, type[RuleServiceError]] = {
    "severity": InvalidSeverityError,
    "category": InvalidCategoryError,
    "conditions": InvalidConditionError,
}


def _translate(exc: ValidationError) -> RuleServiceError:
    """Model validation failure -> service error. Field names and messages only, never submitted values."""
    details = summarize_validation_errors(exc.errors())
    first_field = details[0]["field"].split(".")[0] if details else ""
    error_class = _FIELD_ERRORS.get(first_field, InvalidRuleDataError)
    return error_class(details=details)


def validate_conditions(conditions: Mapping[str, Any]) -> None:
    """Raise InvalidConditionError unless the detection engine can interpret these conditions."""
    try:
        parse_conditions(conditions)
    except InvalidRuleError as exc:
        raise InvalidConditionError(str(exc)) from None


class RuleService:
    def __init__(self, repository: DetectionRuleRepository) -> None:
        self._rules = repository

    def list_rules(
        self,
        *,
        category: str | None = None,
        severity: str | None = None,
        enabled: bool | None = None,
        name: str | None = None,
        page: int = 1,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> RulePage:
        if page < 1:
            raise InvalidRuleDataError("page must be 1 or greater")
        if not 1 <= limit <= MAX_PAGE_LIMIT:
            raise InvalidRuleDataError(f"limit must be between 1 and {MAX_PAGE_LIMIT}")
        rules, total = self._rules.get_rules(
            category=category, severity=severity, enabled=enabled, name=name,
            skip=(page - 1) * limit, limit=limit,
        )
        return RulePage(rules=rules, total=total, page=page, limit=limit)

    def get_rule(self, rule_id: str) -> DetectionRule:
        rule = self._rules.get_rule(rule_id)
        if rule is None:
            raise RuleNotFoundError()
        return rule

    def create_rule(self, data: Mapping[str, Any]) -> DetectionRule:
        """Validate and store a new rule. Timestamps are generated here, never taken from the client."""
        data = {k: v for k, v in data.items() if k not in ("created_at", "updated_at")}
        conditions = data.get("conditions")
        if isinstance(conditions, Mapping):
            validate_conditions(conditions)
        try:
            rule = DetectionRule(**data)
        except ValidationError as exc:
            raise _translate(exc) from None
        try:
            return self._rules.create_rule(rule)
        except DuplicateRecordError:
            raise RuleAlreadyExistsError() from None

    def update_rule(self, rule_id: str, changes: Mapping[str, Any]) -> DetectionRule:
        """Partial update of name, description, category, severity, enabled, conditions.
        rule_id and created_at cannot change; updated_at is set by the server."""
        if not changes:
            raise InvalidRuleDataError("Provide at least one field to update")
        allowed = {"name", "description", "category", "severity", "enabled", "conditions"}
        unknown = sorted(set(changes) - allowed)
        if unknown:
            raise InvalidRuleDataError(f"Fields cannot be updated: {', '.join(unknown)}")
        if "conditions" in changes:
            if not isinstance(changes["conditions"], Mapping):
                raise InvalidConditionError("conditions must be an object")
            validate_conditions(changes["conditions"])
        self.get_rule(rule_id)  # 404 before anything else
        try:
            updated = self._rules.update_rule(rule_id, dict(changes))
        except ValidationError as exc:
            raise _translate(exc) from None
        if updated is None:  # deleted concurrently
            raise RuleNotFoundError()
        return updated

    def set_enabled(self, rule_id: str, enabled: bool) -> DetectionRule:
        if not isinstance(enabled, bool):
            raise InvalidStatusError()
        updated = self._rules.set_enabled(rule_id, enabled)
        if updated is None:
            raise RuleNotFoundError()
        return updated

    def delete_rule(self, rule_id: str, *, force: bool = False) -> None:
        if rule_id in PROTECTED_RULE_IDS and not force:
            if self._rules.get_rule(rule_id) is not None:
                raise RuleProtectedError()
        if not self._rules.delete_rule(rule_id):
            raise RuleNotFoundError()
