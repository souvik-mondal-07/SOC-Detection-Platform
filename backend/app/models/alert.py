"""Alert raised by a detection rule."""

from enum import Enum
from typing import Annotated, Self

from pydantic import Field, model_validator

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


class Alert(MongoModel):
    alert_id: str = Field(pattern=ID_PATTERN)
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    severity: Severity
    status: AlertStatus = AlertStatus.OPEN
    source_ip: IPAddressStr | None = None
    event_ids: Annotated[UniqueIdList, Field(min_length=1, max_length=10_000)]
    created_at: UTCDateTime = Field(default_factory=utc_now)
    updated_at: UTCDateTime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
