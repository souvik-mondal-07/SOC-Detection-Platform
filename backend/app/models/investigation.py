"""Investigation record: a SOC analyst's working file on one or more alerts.

Investigation status is separate from alert status. Changing one never changes the other.
"""

from enum import Enum
from typing import Annotated, Self
from uuid import uuid4

from pydantic import Field, model_validator

from app.models.common import ID_PATTERN, MongoModel, UniqueIdList, UTCDateTime, utc_now

MAX_NOTE_LENGTH = 2000
MAX_NOTES_PER_INVESTIGATION = 500
MAX_ALERTS_PER_INVESTIGATION = 1000


class InvestigationStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"  # the finished state ("completed" in the Step 11 brief); kept as `closed` for compatibility with Step 3


# Allowed status changes. Re-setting the current status is treated as a no-op by the service, not as a transition.
# A closed investigation can only be reopened into in_progress (never straight back to open).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    InvestigationStatus.OPEN.value: frozenset({InvestigationStatus.IN_PROGRESS.value, InvestigationStatus.CLOSED.value}),
    InvestigationStatus.IN_PROGRESS.value: frozenset({InvestigationStatus.OPEN.value, InvestigationStatus.CLOSED.value}),
    InvestigationStatus.CLOSED.value: frozenset({InvestigationStatus.IN_PROGRESS.value}),
}


def new_note_id() -> str:
    return f"note_{uuid4().hex[:16]}"


class InvestigationNote(MongoModel):
    # No author field: there is no authentication yet, so a note cannot be attributed to an analyst.
    note_id: str = Field(default_factory=new_note_id, pattern=ID_PATTERN)
    text: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)
    created_at: UTCDateTime = Field(default_factory=utc_now)


class Investigation(MongoModel):
    investigation_id: str = Field(pattern=ID_PATTERN)
    # Only alert IDs are stored. Alert details are always read from the alerts collection.
    alert_ids: Annotated[UniqueIdList, Field(min_length=1, max_length=MAX_ALERTS_PER_INVESTIGATION)]
    title: str = Field(min_length=1, max_length=200)
    status: InvestigationStatus = InvestigationStatus.OPEN
    notes: list[InvestigationNote] = Field(default_factory=list, max_length=MAX_NOTES_PER_INVESTIGATION)
    created_at: UTCDateTime = Field(default_factory=utc_now)
    updated_at: UTCDateTime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
