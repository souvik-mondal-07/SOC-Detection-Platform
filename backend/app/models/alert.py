"""Alert raised by a detection rule."""

from enum import Enum
from typing import Annotated, Any, Self

from pydantic import Field, model_validator

from app.core.severity import MAX_PRIORITY_SCORE, MIN_PRIORITY_SCORE, base_score
from app.models.common import (
    ID_PATTERN,
    RULE_ID_PATTERN,
    IPAddressStr,
    MongoModel,
    Severity,
    UniqueIdList,
    UTCDateTime,
    utc_now,
)


class AlertStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# -- Step 12: lifecycle --------------------------------------------------------------------------------------------------
# Acknowledgement is NOT a status. It is the `acknowledged_at` timestamp on an alert that is still `open`, so the four
# existing statuses, the status filter, the dashboard counts and open-alert de-duplication keep working unchanged.

MAX_STATUS_REASON_LENGTH = 1000
MAX_STATUS_HISTORY = 200  # the repository keeps only the newest entries beyond this

_OPEN, _INV, _RES, _FP = (s.value for s in (AlertStatus.OPEN, AlertStatus.INVESTIGATING, AlertStatus.RESOLVED, AlertStatus.FALSE_POSITIVE))

# Requested status -> allowed next statuses. Re-requesting the current status is rejected, not treated as a no-op.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    _OPEN: frozenset({_INV, _RES, _FP}),
    _INV: frozenset({_OPEN, _RES, _FP}),
    _RES: frozenset({_OPEN}),  # reopen
    _FP: frozenset({_OPEN}),  # reopen
}
_CLOSED = frozenset({_RES, _FP})


def reason_required(previous: str, new: str) -> bool:
    """Closing an alert (resolved / false positive) and reopening a closed alert both need a written reason."""
    return new in _CLOSED or previous in _CLOSED


class StatusAction(str, Enum):
    STATUS_CHANGE = "status_change"
    ACKNOWLEDGED = "acknowledged"  # status stays open; previous_status == new_status


class AlertStatusChange(MongoModel):
    """One audit entry. There is no actor field: authentication does not exist yet, so a change cannot be attributed."""

    action: StatusAction = StatusAction.STATUS_CHANGE
    previous_status: AlertStatus
    new_status: AlertStatus
    timestamp: UTCDateTime = Field(default_factory=utc_now)
    reason: str | None = Field(default=None, min_length=1, max_length=MAX_STATUS_REASON_LENGTH)


class Alert(MongoModel):
    alert_id: str = Field(pattern=ID_PATTERN)
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    severity: Severity
    # 0-100, see app.services.priority_service. Alerts stored before Step 9 get their severity's base score.
    priority_score: int = Field(ge=MIN_PRIORITY_SCORE, le=MAX_PRIORITY_SCORE)
    priority_reason: str | None = Field(default=None, max_length=200)
    status: AlertStatus = AlertStatus.OPEN
    source_ip: IPAddressStr | None = None
    event_ids: Annotated[UniqueIdList, Field(min_length=1, max_length=10_000)]
    created_at: UTCDateTime = Field(default_factory=utc_now)
    updated_at: UTCDateTime = Field(default_factory=utc_now)
    # Step 12. All optional with defaults, so alerts stored by Steps 8-11 load unchanged.
    acknowledged_at: UTCDateTime | None = None
    resolution_note: str | None = Field(default=None, max_length=MAX_STATUS_REASON_LENGTH)  # why it is resolved / false positive
    status_history: list[AlertStatusChange] = Field(default_factory=list, max_length=MAX_STATUS_HISTORY)

    @model_validator(mode="before")
    @classmethod
    def _default_priority_score(cls, data: Any) -> Any:
        """Backward compatibility: documents without priority_score fall back to the base score."""
        if isinstance(data, dict) and data.get("priority_score") is None and data.get("severity") is not None:
            try:
                return {**data, "priority_score": base_score(data["severity"])}
            except ValueError:
                return data  # the severity validator reports the real error
        return data

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
