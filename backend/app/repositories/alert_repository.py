import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.database import COLLECTION_ALERTS
from app.core.severity import MAX_PRIORITY_SCORE, MIN_PRIORITY_SCORE
from app.models.alert import MAX_STATUS_HISTORY, Alert, AlertStatus
from app.repositories.base import BaseRepository, translate_db_errors

MAX_ALERT_PAGE_LIMIT = 100  # cap for one page of the alert API


class AlertRepository(BaseRepository[Alert]):
    model = Alert
    collection_name = COLLECTION_ALERTS
    id_field = "alert_id"
    indexes = (
        IndexModel([("alert_id", ASCENDING)], name="uq_alert_id", unique=True),
        IndexModel([("created_at", DESCENDING)], name="ix_created_at"),  # newest alerts first
        # Step 9: default list order (priority_score DESC, created_at DESC) and priority_min/max range filters.
        IndexModel([("priority_score", DESCENDING), ("created_at", DESCENDING)], name="ix_priority_created_at"),
        # Step 9: the analyst triage queue, e.g. open alerts by priority.
        IndexModel([("status", ASCENDING), ("priority_score", DESCENDING), ("created_at", DESCENDING)], name="ix_status_priority_created_at"),
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
        priority_min: int | None = None,
        priority_max: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Alert], int]:
        """One page of alerts, highest priority first (ties: newest first), plus the total matching the filters.

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
        for name, bound in (("priority_min", priority_min), ("priority_max", priority_max)):
            if bound is not None and not MIN_PRIORITY_SCORE <= bound <= MAX_PRIORITY_SCORE:
                raise ValueError(f"{name} must be between {MIN_PRIORITY_SCORE} and {MAX_PRIORITY_SCORE}")
        if priority_min is not None and priority_max is not None and priority_min > priority_max:
            raise ValueError("priority_min cannot be greater than priority_max")
        if priority_min is not None or priority_max is not None:
            query["priority_score"] = {
                **({"$gte": priority_min} if priority_min is not None else {}),
                **({"$lte": priority_max} if priority_max is not None else {}),
            }
        with translate_db_errors():
            total = self._collection.count_documents(query)
            cursor = (
                self._collection.find(query, {"_id": 0})
                .sort([("priority_score", DESCENDING), ("created_at", DESCENDING), ("alert_id", DESCENDING)])
                .skip(skip)
                .limit(limit)
            )
            documents = list(cursor)
        return [Alert.from_document(document) for document in documents], total

    def get_alerts_by_ids(self, alert_ids: Sequence[str]) -> list[Alert]:
        """The stored alerts among `alert_ids` (missing IDs are simply absent). Order is not guaranteed."""
        ids = list(dict.fromkeys(alert_ids))
        if not ids:
            return []
        with translate_db_errors():
            documents = list(self._collection.find({"alert_id": {"$in": ids}}, {"_id": 0}))
        return [Alert.from_document(document) for document in documents]

    def update_alert(self, alert_id: str, changes: Mapping[str, Any]) -> Alert | None:
        """Partial update (re-validated). alert_id and created_at are immutable. None if not found."""
        return self.update(alert_id, changes)

    # -- Step 12: lifecycle ----------------------------------------------------------------------

    @staticmethod
    def _status_filter(status: str) -> dict[str, Any]:
        # Alerts stored without a status are read as open by the Alert model, so they match "open" here too.
        if status == AlertStatus.OPEN.value:
            return {"$or": [{"status": "open"}, {"status": {"$exists": False}}]}
        return {"status": status}

    def apply_transition(
        self,
        alert_id: str,
        *,
        expected_status: str,
        changes: Mapping[str, Any],
        history_entry: Mapping[str, Any],
        require_unacknowledged: bool = False,
    ) -> bool:
        """Compare-and-set in ONE atomic update.

        The write only happens if the alert still has `expected_status` (and, for acknowledgement, no acknowledged_at yet),
        so two concurrent requests can never both apply. `changes` is applied with $set and `history_entry` is appended
        (newest MAX_STATUS_HISTORY kept). Only the fields in `changes` are touched: severity, priority, rule and events never are.
        Returns False when nothing matched (alert missing, or its status changed first).
        """
        query: dict[str, Any] = {"alert_id": alert_id, **self._status_filter(expected_status)}
        if require_unacknowledged:
            query["acknowledged_at"] = None  # matches null or missing
        update = {
            "$set": dict(changes),
            "$push": {"status_history": {"$each": [dict(history_entry)], "$slice": -MAX_STATUS_HISTORY}},
        }
        with translate_db_errors():
            result = self._collection.update_one(query, update)
        return result.matched_count == 1

    def get_stats(self) -> dict[str, Any]:
        """Exact alert counts, computed inside MongoDB with one aggregation plus one count."""
        with translate_db_errors():
            groups = list(
                self._collection.aggregate(
                    [{"$group": {"_id": {"status": "$status", "severity": "$severity"}, "count": {"$sum": 1}}}]
                )
            )
            acknowledged_open = self._collection.count_documents({**self._status_filter("open"), "acknowledged_at": {"$ne": None}})
        by_status = {status.value: 0 for status in AlertStatus}
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        active = high_critical_active = 0
        for group in groups:
            status = group["_id"].get("status") or "open"  # stored without a status = open
            severity = group["_id"].get("severity")
            count = group["count"]
            by_status[status] = by_status.get(status, 0) + count
            if severity is not None:
                by_severity[severity] = by_severity.get(severity, 0) + count
            if status in ("open", "investigating"):
                active += count
                if severity in ("high", "critical"):
                    high_critical_active += count
        return {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "by_severity": by_severity,
            "active": active,
            "high_critical_active": high_critical_active,
            "acknowledged_open": acknowledged_open,
        }

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
