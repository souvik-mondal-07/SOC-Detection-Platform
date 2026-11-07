"""Request and response schemas for the investigation API (Step 11).

Clients can set only: title, status, alert links and note text. They cannot supply
investigation_id, note_id, timestamps or any alert field.

The investigation API has no authentication yet and is for local development only.
"""

from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.models.alert import Alert
from app.models.common import ID_PATTERN
from app.models.investigation import (
    MAX_NOTE_LENGTH,
    Investigation,
    InvestigationNote,
    InvestigationStatus,
)

MAX_LINK_REQUEST_ALERTS = 100  # alerts per create/link request
MAX_EVENT_IDS_IN_CONTEXT = 50  # event IDs returned per linked alert; event_count has the full number

AlertId = Annotated[str, Field(pattern=ID_PATTERN, max_length=64)]


def _ensure_unique(values: list[str]) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError("alert_ids must not contain duplicates")
    return values


AlertIdList = Annotated[list[AlertId], Field(min_length=1, max_length=MAX_LINK_REQUEST_ALERTS), AfterValidator(_ensure_unique)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InvestigationCreateRequest(_Request):
    title: str = Field(min_length=1, max_length=200)
    alert_ids: AlertIdList


class InvestigationUpdateRequest(_Request):
    """Only the title and the investigation status can be changed here (alert severity, priority and status cannot)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: InvestigationStatus | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("provide title and/or status")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("title and status cannot be null")
        return self


class LinkAlertsRequest(_Request):
    alert_ids: AlertIdList


class NoteCreateRequest(_Request):
    text: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)


# -- Responses ------------------------------------------------------------------------


class NoteOut(BaseModel):
    note_id: str
    text: str
    created_at: datetime


class LinkedAlert(BaseModel):
    """Context for one linked alert, read live from the alerts collection.

    If the alert no longer exists, available is False and only alert_id is filled in.
    """

    alert_id: str
    available: bool = True
    rule_id: str | None = None
    title: str | None = None
    severity: str | None = None
    priority_score: int | None = None
    status: str | None = None
    source_ip: str | None = None
    created_at: datetime | None = None
    event_count: int = 0
    event_ids: list[str] = Field(default_factory=list)  # first MAX_EVENT_IDS_IN_CONTEXT only


class InvestigationListItem(BaseModel):
    investigation_id: str
    title: str
    status: str
    alert_count: int
    note_count: int
    created_at: datetime
    updated_at: datetime


class InvestigationDetail(InvestigationListItem):
    alert_ids: list[str]
    alerts: list[LinkedAlert]  # same order as alert_ids
    notes: list[NoteOut]  # oldest first
    unavailable_alert_count: int = 0


def to_list_item(investigation: Investigation) -> InvestigationListItem:
    return InvestigationListItem(
        investigation_id=investigation.investigation_id,
        title=investigation.title,
        status=investigation.status,
        alert_count=len(investigation.alert_ids),
        note_count=len(investigation.notes),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
    )


def to_note(note: InvestigationNote) -> NoteOut:
    return NoteOut(note_id=note.note_id, text=note.text, created_at=note.created_at)


def to_linked_alert(alert: Alert) -> LinkedAlert:
    return LinkedAlert(
        alert_id=alert.alert_id,
        rule_id=alert.rule_id,
        title=alert.title,
        severity=alert.severity,
        priority_score=alert.priority_score,
        status=alert.status,
        source_ip=alert.source_ip,
        created_at=alert.created_at,
        event_count=len(alert.event_ids),
        event_ids=alert.event_ids[:MAX_EVENT_IDS_IN_CONTEXT],
    )


def to_detail(investigation: Investigation, alerts_by_id: dict[str, Alert]) -> InvestigationDetail:
    linked = [
        to_linked_alert(alerts_by_id[alert_id]) if alert_id in alerts_by_id else LinkedAlert(alert_id=alert_id, available=False)
        for alert_id in investigation.alert_ids
    ]
    return InvestigationDetail(
        **to_list_item(investigation).model_dump(),
        alert_ids=list(investigation.alert_ids),
        alerts=linked,
        notes=[to_note(n) for n in investigation.notes],
        unavailable_alert_count=sum(1 for item in linked if not item.available),
    )


class InvestigationResponse(BaseModel):
    success: bool = True
    investigation: InvestigationDetail


class InvestigationListResponse(BaseModel):
    success: bool = True
    page: int
    limit: int
    total: int
    count: int
    investigations: list[InvestigationListItem]
