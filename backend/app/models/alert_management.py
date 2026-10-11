"""Response schemas for the alert API (Step 8).

Alerts are generated server-side only. No request schema accepts alert_id,
rule_id, severity, status or timestamps, so a client cannot set them.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.alert import Alert


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


class AlertDetail(AlertListItem):
    description: str
    event_ids: list[str]
    updated_at: datetime


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
