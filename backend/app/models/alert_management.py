"""Response schemas for the alert API (Step 8).

Alerts are generated server-side only. No request schema accepts alert_id,
rule_id, severity, status or timestamps, so a client cannot set them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.alert import MAX_STATUS_REASON_LENGTH, Alert, AlertStatus


class AlertSummary(BaseModel):
    alert_id: str
    rule_id: str
    title: str
    severity: str
    priority_score: int
    priority_reason: str | None = None
    status: str


class AlertListItem(AlertSummary):
    source_ip: str | None = None
    created_at: datetime
    acknowledged_at: datetime | None = None


class StatusHistoryItem(BaseModel):
    action: str
    previous_status: str
    new_status: str
    timestamp: datetime
    reason: str | None = None


class AlertDetail(AlertListItem):
    description: str
    event_ids: list[str]
    updated_at: datetime
    resolution_note: str | None = None
    status_history: list[StatusHistoryItem] = Field(default_factory=list)  # oldest first


def to_detail(alert: Alert) -> AlertDetail:
    return AlertDetail(**alert.model_dump(mode="python"))


def to_list_item(alert: Alert) -> AlertListItem:
    return AlertListItem(**alert.model_dump(include=set(AlertListItem.model_fields)))


def to_summary(alert: Alert) -> AlertSummary:
    return AlertSummary(**alert.model_dump(include=set(AlertSummary.model_fields)))


class FailedEvent(BaseModel):
    event_id: str
    error_code: str
    message: str


class AlertGenerationResponse(BaseModel):
    success: bool = True
    event_id: str
    alerts_created: int
    duplicates_skipped: int = 0
    alerts: list[AlertSummary]


class BatchAlertGenerationResponse(BaseModel):
    success: bool = True
    events_evaluated: int
    alerts_created: int
    duplicates_skipped: int = 0
    alerts: list[AlertSummary]
    failed_events: list[FailedEvent] = Field(default_factory=list)


class AlertListResponse(BaseModel):
    success: bool = True
    page: int
    limit: int
    total: int
    count: int
    alerts: list[AlertListItem]


class AlertResponse(BaseModel):
    success: bool = True
    alert: AlertDetail


class AlertStatusUpdateRequest(BaseModel):
    """PATCH /alerts/{id}/status. Only these two fields exist; anything else (severity, priority_score, ...) is a 422."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: AlertStatus
    reason: str | None = Field(default=None, max_length=MAX_STATUS_REASON_LENGTH, description="Resolution note / false-positive reason / reopen reason")

    @field_validator("reason")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None  # whitespace-only becomes None; the service decides whether a reason is required


class AlertStatsResponse(BaseModel):
    """Exact counts computed by MongoDB over all alerts (never derived from a page of results)."""

    success: bool = True
    total: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    active: int  # open + investigating
    high_critical_active: int  # severity high/critical and status open/investigating
    acknowledged_open: int  # open alerts that have been acknowledged
