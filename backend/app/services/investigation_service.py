"""Investigation workflow: create, link alerts, take notes, change status.

All business rules live here; routes only translate HTTP, and MongoDB access stays in the repositories.
Alerts are the source of truth: an investigation stores alert IDs only, and alert details are read live.
This service never modifies an alert (no status, severity or priority changes).
"""

import logging
from collections.abc import Sequence

from app.core.errors import DuplicateRecordError
from app.models.alert import Alert
from app.models.common import utc_now
from app.models.investigation import (
    ALLOWED_TRANSITIONS,
    MAX_ALERTS_PER_INVESTIGATION,
    MAX_NOTES_PER_INVESTIGATION,
    Investigation,
    InvestigationNote,
)
from app.repositories.alert_repository import AlertRepository
from app.repositories.investigation_repository import InvestigationRepository

logger = logging.getLogger("soc.investigations")

MAX_ID_ATTEMPTS = 5


class InvestigationServiceError(Exception):
    """Base class. `message` is safe to show to clients; `status_code` is the HTTP status the API uses."""

    status_code = 400
    error_code = "INVESTIGATION_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvestigationNotFoundError(InvestigationServiceError):
    status_code = 404
    error_code = "INVESTIGATION_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Investigation not found")


class AlertsNotFoundError(InvestigationServiceError):
    status_code = 404
    error_code = "ALERT_NOT_FOUND"

    def __init__(self, missing: Sequence[str]) -> None:
        super().__init__(f"Alert not found: {', '.join(missing)}")  # IDs were validated against ID_PATTERN


class AlertNotLinkedError(InvestigationServiceError):
    status_code = 404
    error_code = "ALERT_NOT_LINKED"

    def __init__(self) -> None:
        super().__init__("Alert is not linked to this investigation")


class DuplicateAlertLinkError(InvestigationServiceError):
    status_code = 409
    error_code = "ALERT_ALREADY_LINKED"

    def __init__(self, duplicates: Sequence[str]) -> None:
        super().__init__(f"Alert already linked: {', '.join(duplicates)}")


class InvalidStatusTransitionError(InvestigationServiceError):
    status_code = 409
    error_code = "INVALID_STATUS_TRANSITION"

    def __init__(self, current: str, requested: str) -> None:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[current]))
        super().__init__(f"Cannot change status from '{current}' to '{requested}'. Allowed: {allowed}")


class LastAlertError(InvestigationServiceError):
    status_code = 409
    error_code = "LAST_ALERT"

    def __init__(self) -> None:
        super().__init__("An investigation must keep at least one linked alert")


class LimitExceededError(InvestigationServiceError):
    status_code = 409
    error_code = "LIMIT_EXCEEDED"


class InvestigationIdGenerationError(InvestigationServiceError):
    status_code = 503
    error_code = "INVESTIGATION_ID_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("Could not allocate a unique investigation ID")


class InvestigationService:
    def __init__(self, investigation_repository: InvestigationRepository, alert_repository: AlertRepository) -> None:
        self._investigations = investigation_repository
        self._alerts = alert_repository

    # -- reads ---------------------------------------------------------------------------

    def list_investigations(
        self, *, status: str | None, alert_id: str | None, title_contains: str | None, page: int, limit: int
    ) -> tuple[list[Investigation], int]:
        return self._investigations.get_investigations(
            status=status, alert_id=alert_id, title_contains=title_contains, skip=(page - 1) * limit, limit=limit
        )

    def get(self, investigation_id: str) -> Investigation:
        investigation = self._investigations.get_investigation_by_id(investigation_id)
        if investigation is None:
            raise InvestigationNotFoundError()
        return investigation

    def linked_alerts(self, investigation: Investigation) -> dict[str, Alert]:
        """Current alert records for the investigation, keyed by alert_id. Deleted alerts are simply absent."""
        return {alert.alert_id: alert for alert in self._alerts.get_alerts_by_ids(investigation.alert_ids)}

    # -- writes --------------------------------------------------------------------------

    def create(self, title: str, alert_ids: Sequence[str]) -> Investigation:
        self._require_alerts_exist(alert_ids)
        for _ in range(MAX_ID_ATTEMPTS):
            now = utc_now()
            investigation = Investigation(
                investigation_id=self._investigations.next_investigation_id(now),
                title=title,
                alert_ids=list(alert_ids),
                created_at=now,
                updated_at=now,
            )
            try:
                created = self._investigations.create_investigation(investigation)
            except DuplicateRecordError:
                continue  # another writer took this number; pick the next one
            logger.info("Investigation %s created with %d alert(s)", created.investigation_id, len(alert_ids))
            return created
        raise InvestigationIdGenerationError()

    def update(self, investigation_id: str, *, title: str | None = None, status: str | None = None) -> Investigation:
        current = self.get(investigation_id)
        changes: dict[str, str] = {}
        if title is not None and title != current.title:
            changes["title"] = title
        if status is not None and status != current.status:
            if status not in ALLOWED_TRANSITIONS.get(current.status, frozenset()):
                raise InvalidStatusTransitionError(current.status, status)
            changes["status"] = status
        if not changes:
            return current  # nothing to change; updated_at stays as it was
        updated = self._investigations.update(investigation_id, changes)
        if updated is None:  # deleted between the read and the write
            raise InvestigationNotFoundError()
        return updated

    def link_alerts(self, investigation_id: str, alert_ids: Sequence[str]) -> Investigation:
        current = self.get(investigation_id)
        duplicates = [alert_id for alert_id in alert_ids if alert_id in current.alert_ids]
        if duplicates:
            raise DuplicateAlertLinkError(duplicates)
        if len(current.alert_ids) + len(alert_ids) > MAX_ALERTS_PER_INVESTIGATION:
            raise LimitExceededError(f"An investigation can link at most {MAX_ALERTS_PER_INVESTIGATION} alerts")
        self._require_alerts_exist(alert_ids)
        if not self._investigations.add_alert_ids(investigation_id, list(alert_ids)):
            raise InvestigationNotFoundError()
        return self.get(investigation_id)

    def unlink_alert(self, investigation_id: str, alert_id: str) -> Investigation:
        current = self.get(investigation_id)
        if alert_id not in current.alert_ids:
            raise AlertNotLinkedError()
        if len(current.alert_ids) == 1:
            raise LastAlertError()
        if not self._investigations.remove_alert_id(investigation_id, alert_id):
            # Changed concurrently: re-read to report the accurate reason.
            latest = self.get(investigation_id)
            raise AlertNotLinkedError() if alert_id not in latest.alert_ids else LastAlertError()
        return self.get(investigation_id)

    def add_note(self, investigation_id: str, text: str) -> Investigation:
        current = self.get(investigation_id)
        if len(current.notes) >= MAX_NOTES_PER_INVESTIGATION:
            raise LimitExceededError(f"An investigation can hold at most {MAX_NOTES_PER_INVESTIGATION} notes")
        if not self._investigations.add_note(investigation_id, InvestigationNote(text=text)):
            raise InvestigationNotFoundError()
        return self.get(investigation_id)

    # -- helpers -------------------------------------------------------------------------

    def _require_alerts_exist(self, alert_ids: Sequence[str]) -> None:
        found = {alert.alert_id for alert in self._alerts.get_alerts_by_ids(alert_ids)}
        missing = [alert_id for alert_id in alert_ids if alert_id not in found]
        if missing:
            raise AlertsNotFoundError(missing)
