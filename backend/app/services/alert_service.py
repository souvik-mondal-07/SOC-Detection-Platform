"""Alert generation: turn matched detection results into persistent alerts.

This service contains no detection logic. It asks DetectionService for results,
then for every match it loads the rule (the source of truth for severity and
title), builds an Alert, skips duplicates and stores it via AlertRepository.
Alerts are never created by ingestion, the rule evaluator or the engine.

Duplicate prevention: an alert is skipped when an *open* alert already exists with
the same rule_id, the same source_ip (or both without one) and at least one
contributing event in common. Re-evaluating the same event or burst therefore
creates no new alert; a genuinely new burst (no shared events) does.
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.errors import DuplicateRecordError
from app.detection.result import DetectionResult, EventDetection
from app.models.alert import ALLOWED_TRANSITIONS, Alert, AlertStatus, StatusAction, reason_required
from app.models.common import ID_PATTERN, utc_now
from app.models.event import SecurityEvent
from app.models.rule import DetectionRule
from app.repositories.alert_repository import AlertRepository
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.services.detection_service import DetectionService
from app.services.ingestion_service import EventNotFoundError
from app.services.priority_service import PriorityService

logger = logging.getLogger("soc.alerts")

MAX_ID_ATTEMPTS = 5
MAX_ALERT_EVENT_IDS = 10_000
_EVENT_ID = re.compile(ID_PATTERN)


class AlertServiceError(Exception):
    """Base class. `error_code` is stable and `message` is safe to show to clients."""

    error_code = "ALERT_ERROR"
    message = "Alert generation failed"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class RuleNotFoundForAlertError(AlertServiceError):
    error_code = "RULE_NOT_FOUND"
    message = "The detection rule for this match no longer exists"


class InvalidDetectionResultError(AlertServiceError):
    error_code = "INVALID_DETECTION_RESULT"
    message = "The detection result cannot be turned into an alert"


class AlertIdGenerationError(AlertServiceError):
    error_code = "ALERT_ID_UNAVAILABLE"
    message = "Could not allocate a unique alert ID"


# -- Step 12: lifecycle errors. `status_code` is the HTTP status the route uses; messages are safe to show to clients. --

class AlertNotFoundError(AlertServiceError):
    error_code = "ALERT_NOT_FOUND"
    message = "Alert not found"
    status_code = 404


class InvalidStatusTransitionError(AlertServiceError):
    error_code = "INVALID_STATUS_TRANSITION"
    message = "This status change is not allowed"
    status_code = 409


class StatusConflictError(AlertServiceError):
    error_code = "STATUS_CONFLICT"
    message = "The alert was changed by someone else. Reload it and try again"
    status_code = 409


class ReasonRequiredError(AlertServiceError):
    error_code = "REASON_REQUIRED"
    message = "A reason is required for this status change"
    status_code = 422


@dataclass
class GenerationOutcome:
    created: list[Alert] = field(default_factory=list)
    duplicates_skipped: int = 0
    # (event_id, error_code, message) for events that could not be processed
    failures: list[tuple[str, str, str]] = field(default_factory=list)
    events_evaluated: int = 0


class AlertService:
    def __init__(
        self,
        alert_repository: AlertRepository,
        rule_repository: DetectionRuleRepository,
        event_repository: EventRepository,
        detection_service: DetectionService | None = None,
        priority_service: PriorityService | None = None,
    ) -> None:
        self._alerts = alert_repository
        self._rules = rule_repository
        self._events = event_repository
        self._detection = detection_service or DetectionService(event_repository, rule_repository)
        self._priority = priority_service or PriorityService()

    # -- Step 12: lifecycle ------------------------------------------------------------------------
    # Lifecycle changes touch only status, updated_at, acknowledged_at, resolution_note and status_history. They never run
    # detection, create alerts, or change severity, priority, rule, source IP or event references.
    # Authentication does not exist yet, so history entries carry no actor.

    def change_status(self, alert_id: str, new_status: AlertStatus | str, reason: str | None = None) -> Alert:
        """Move an alert to `new_status` if the transition is allowed. Atomic: a concurrent change makes this fail, never overwrite."""
        target = AlertStatus(new_status).value
        alert = self._require_alert(alert_id)
        current = AlertStatus(alert.status).value
        if target not in ALLOWED_TRANSITIONS[current]:
            if target == current:
                raise InvalidStatusTransitionError(f"The alert is already {_label(current)}")
            raise InvalidStatusTransitionError(f"An alert that is {_label(current)} cannot be changed to {_label(target)}")
        reason = (reason or "").strip() or None
        if reason is None and reason_required(current, target):
            if current in (AlertStatus.RESOLVED.value, AlertStatus.FALSE_POSITIVE.value):
                raise ReasonRequiredError("A reason is required to reopen an alert")
            raise ReasonRequiredError("A resolution note is required" if target == AlertStatus.RESOLVED.value else "A false-positive reason is required")

        now = max(utc_now(), alert.created_at)  # updated_at may never be earlier than created_at
        changes: dict = {"status": target, "updated_at": now}
        if target in (AlertStatus.RESOLVED.value, AlertStatus.FALSE_POSITIVE.value):
            changes["resolution_note"] = reason
        elif current in (AlertStatus.RESOLVED.value, AlertStatus.FALSE_POSITIVE.value):
            changes.update(resolution_note=None, acknowledged_at=None)  # reopened: back in the triage queue, history keeps the old note
        entry = {"action": StatusAction.STATUS_CHANGE.value, "previous_status": current, "new_status": target, "timestamp": now, "reason": reason}
        if not self._alerts.apply_transition(alert_id, expected_status=current, changes=changes, history_entry=entry):
            self._raise_conflict(alert_id)
        logger.info("Alert %s: %s -> %s", alert_id, current, target)
        return self._require_alert(alert_id)

    def acknowledge(self, alert_id: str) -> Alert:
        """Record that an analyst has seen an open alert. The status stays `open`."""
        alert = self._require_alert(alert_id)
        if alert.status != AlertStatus.OPEN.value:
            raise InvalidStatusTransitionError(f"Only open alerts can be acknowledged; this alert is {_label(alert.status)}")
        if alert.acknowledged_at is not None:
            raise InvalidStatusTransitionError("The alert is already acknowledged")
        now = max(utc_now(), alert.created_at)
        entry = {"action": StatusAction.ACKNOWLEDGED.value, "previous_status": "open", "new_status": "open", "timestamp": now, "reason": None}
        applied = self._alerts.apply_transition(
            alert_id, expected_status="open", changes={"acknowledged_at": now, "updated_at": now}, history_entry=entry, require_unacknowledged=True
        )
        if not applied:
            self._raise_conflict(alert_id)
        logger.info("Alert %s acknowledged", alert_id)
        return self._require_alert(alert_id)

    def _require_alert(self, alert_id: str) -> Alert:
        alert = self._alerts.get_alert_by_id(alert_id)
        if alert is None:
            raise AlertNotFoundError()
        return alert

    def _raise_conflict(self, alert_id: str) -> None:
        self._require_alert(alert_id)  # deleted in the meantime -> 404
        raise StatusConflictError()

    # -- generation from stored events -----------------------------------------------

    def generate_for_event_id(self, event_id: str) -> GenerationOutcome:
        """Evaluate one stored event and persist alerts for matches. Raises EventNotFoundError."""
        event = self._events.get_event_by_id(event_id)
        if event is None:
            raise EventNotFoundError(event_id)
        outcome = GenerationOutcome(events_evaluated=1)
        self._process_event(event, self._rules.get_enabled_rules(), outcome)
        if outcome.failures:  # single-event call: surface the failure instead of hiding it
            raise AlertServiceError(outcome.failures[0][2])
        return outcome

    def generate_for_event_ids(self, event_ids: Sequence[str]) -> GenerationOutcome:
        """Evaluate several events. One bad event never stops the others."""
        unique_ids = list(dict.fromkeys(event_ids))
        found = {event.event_id: event for event in self._events.get_events_by_ids(unique_ids)}
        rules = self._rules.get_enabled_rules()
        outcome = GenerationOutcome()
        for event_id in unique_ids:
            event = found.get(event_id)
            if event is None:
                outcome.failures.append((event_id, "EVENT_NOT_FOUND", "Event not found"))
                continue
            outcome.events_evaluated += 1
            self._process_event(event, rules, outcome)
        return outcome

    def _process_event(self, event: SecurityEvent, rules: Sequence[DetectionRule], outcome: GenerationOutcome) -> None:
        try:
            detection = self._detection.evaluate_event(event, rules)
            self.create_alerts_from_detection(detection, event, outcome)
        except AlertServiceError as exc:
            outcome.failures.append((event.event_id, exc.error_code, exc.message))
        # DatabaseUnavailableError is deliberately not caught: it fails the whole request (503).

    # -- generation from detection results -------------------------------------------

    def create_alerts_from_detection(
        self, detection: EventDetection, event: SecurityEvent | None = None, outcome: GenerationOutcome | None = None
    ) -> GenerationOutcome:
        """Create alerts for every matched result. Non-matches are ignored."""
        outcome = outcome or GenerationOutcome()
        for result in detection.matches:
            try:
                alert = self.create_alert_from_result(result, event)
            except AlertServiceError as exc:
                outcome.failures.append((result.event_id, exc.error_code, exc.message))
                continue
            if alert is None:
                outcome.duplicates_skipped += 1
            else:
                outcome.created.append(alert)
        return outcome

    def create_alert_from_result(self, result: DetectionResult, event: SecurityEvent | None = None) -> Alert | None:
        """Persist one alert for a matched result.

        Returns None when the result is not a match or an equivalent open alert exists.
        """
        if not result.matched:
            return None
        rule = self._rules.get_rule(result.rule_id)
        if rule is None:
            raise RuleNotFoundForAlertError()

        event_ids = list(dict.fromkeys([*result.matched_event_ids, result.event_id]))[:MAX_ALERT_EVENT_IDS]
        if not all(_EVENT_ID.match(i) for i in event_ids):
            raise InvalidDetectionResultError()
        source_ip = _source_ip(result, event)

        if self._alerts.find_open_duplicate(rule.rule_id, source_ip, event_ids) is not None:
            return None

        # Priority is derived from the rule's severity plus detection context; never from the event.
        priority = self._priority.calculate(
            rule.severity,
            event_count=len(event_ids),
            correlated=bool(result.details.get("correlation_field") and result.details.get("correlation_value")),
            last_event_at=event.timestamp if event is not None else None,
        )

        for _ in range(MAX_ID_ATTEMPTS):
            now = utc_now()
            try:
                alert = Alert(
                    alert_id=self._alerts.next_alert_id(now),
                    rule_id=rule.rule_id,
                    title=f"{rule.name} Detected"[:200],
                    description=_describe(rule, result, source_ip, len(event_ids)),
                    severity=rule.severity,  # rule is the source of truth, never the event or result
                    priority_score=priority.score,
                    priority_reason=priority.reason,
                    status=AlertStatus.OPEN,
                    source_ip=source_ip,
                    event_ids=event_ids,
                    created_at=now,
                    updated_at=now,
                )
            except ValidationError:
                raise InvalidDetectionResultError() from None
            try:
                return self._alerts.create_alert(alert)
            except DuplicateRecordError:
                continue  # another writer took this ID; pick the next one
        raise AlertIdGenerationError()


def _label(status: str) -> str:
    return status.replace("_", " ")


def _source_ip(result: DetectionResult, event: SecurityEvent | None) -> str | None:
    """Source IP from the detection context only; never invented."""
    details = result.details
    if details.get("correlation_field") == "source_ip" and details.get("correlation_value"):
        return str(details["correlation_value"])
    return event.source_ip if event is not None else None


def _describe(rule: DetectionRule, result: DetectionResult, source_ip: str | None, event_count: int) -> str:
    parts = [f"Suspicious activity matching rule {rule.rule_id} ({rule.name}) was detected: {result.reason}."]
    if source_ip:
        parts.append(f"Source IP: {source_ip}.")
    parts.append(f"Contributing events: {event_count}.")
    window = result.details.get("window_minutes")
    if window:
        parts.append(f"Detection window: {window} minutes.")
    parts.append("This requires investigation.")
    return " ".join(parts)[:1000]
