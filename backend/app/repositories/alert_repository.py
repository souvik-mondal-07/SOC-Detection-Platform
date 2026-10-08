import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.database import COLLECTION_ALERTS
from app.models.alert import Alert
from app.repositories.base import BaseRepository, translate_db_errors

MAX_ALERT_PAGE_LIMIT = 100  # cap for one page of the alert API


class AlertRepository(BaseRepository[Alert]):
    model = Alert
    collection_name = COLLECTION_ALERTS
    id_field = "alert_id"
    indexes = (
        IndexModel([("alert_id", ASCENDING)], name="uq_alert_id", unique=True),
        IndexModel([("created_at", DESCENDING)], name="ix_created_at"),  # newest alerts first
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="ix_status_created_at"),  # triage queue
        IndexModel([("severity", ASCENDING), ("created_at", DESCENDING)], name="ix_severity_created_at"),  # filter by severity
        IndexModel([("rule_id", ASCENDING), ("created_at", DESCENDING)], name="ix_rule_id_created_at"),  # alerts per rule, tuning
        IndexModel([("source_ip", ASCENDING), ("created_at", DESCENDING)], name="ix_source_ip_created_at"),  # alerts for one IP
    )

    # -- Step 8: alert persistence ---------------------------------------------------

    def create_alert(self, alert: Alert) -> Alert:
        """Insert an alert. Raises DuplicateRecordError if the alert_id already exists."""
        return self.create(alert)

    def get_alert_by_id(self, alert_id: str) -> Alert | None:
        return self.find_by_id(alert_id)

    def get_alerts(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        rule_id: str | None = None,
        source_ip: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Alert], int]:
        """One page of alerts, newest first, plus the total matching the filters.

        Filtering, counting, sorting, skipping and limiting all happen inside MongoDB.
        """
        if not 1 <= limit <= MAX_ALERT_PAGE_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_ALERT_PAGE_LIMIT}")
        if skip < 0:
            raise ValueError("skip must be 0 or greater")
        query = {
            key: value
            for key, value in (("status", status), ("severity", severity), ("rule_id", rule_id), ("source_ip", source_ip))
            if value is not None
        }
        with translate_db_errors():
            total = self._collection.count_documents(query)
            cursor = (
                self._collection.find(query, {"_id": 0})
                .sort([("created_at", DESCENDING), ("alert_id", DESCENDING)])
                .skip(skip)
                .limit(limit)
            )
            documents = list(cursor)
        return [Alert.from_document(document) for document in documents], total

    def update_alert(self, alert_id: str, changes: Mapping[str, Any]) -> Alert | None:
        """Partial update (re-validated). alert_id and created_at are immutable. None if not found."""
        return self.update(alert_id, changes)

    def find_open_duplicate(self, rule_id: str, source_ip: str | None, event_ids: Sequence[str]) -> Alert | None:
        """An open alert from the same rule and source IP that shares at least one event.

        `source_ip=None` matches alerts that have no source IP.
        """
        query = {"rule_id": rule_id, "status": "open", "source_ip": source_ip, "event_ids": {"$in": list(event_ids)}}
        with translate_db_errors():
            document = self._collection.find_one(query, {"_id": 0})
        return Alert.from_document(document) if document else None

    def next_alert_id(self, now: datetime) -> str:
        """Next readable ID for `now`'s UTC day, e.g. ALT-20261007-000001.

        The sequence continues from the highest stored ID for that day. Two writers
        can pick the same number; the unique index rejects one and the caller retries.
        """
        prefix = f"ALT-{now:%Y%m%d}-"
        with translate_db_errors():
            latest = self._collection.find_one(
                {"alert_id": {"$regex": f"^{re.escape(prefix)}"}}, {"_id": 0, "alert_id": 1}, sort=[("alert_id", DESCENDING)]
            )
        number = 1
        if latest:
            try:
                number = int(latest["alert_id"][len(prefix):]) + 1
            except ValueError:
                number = 1
        return f"{prefix}{number:06d}"
