"""Basic investigation record (full workflow comes in a later step)."""

from enum import Enum
from typing import Annotated, Self

from pydantic import Field, model_validator

from app.models.common import ID_PATTERN, MongoModel, UniqueIdList, UTCDateTime, utc_now


class InvestigationStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class InvestigationNote(MongoModel):
    text: str = Field(min_length=1, max_length=2000)
    created_at: UTCDateTime = Field(default_factory=utc_now)


class Investigation(MongoModel):
    investigation_id: str = Field(pattern=ID_PATTERN)
    alert_ids: Annotated[UniqueIdList, Field(min_length=1, max_length=1000)]
    title: str = Field(min_length=1, max_length=200)
    status: InvestigationStatus = InvestigationStatus.OPEN
    notes: list[InvestigationNote] = Field(default_factory=list)
    created_at: UTCDateTime = Field(default_factory=utc_now)
    updated_at: UTCDateTime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
