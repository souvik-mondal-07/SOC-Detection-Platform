"""Request/response schemas for the log-parsing endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.event import MAX_BATCH_SIZE, FieldError, SecurityEvent

MAX_RAW_LOG_CHARS = 10_000


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1, max_length=64)
    # Text formats (syslog, web) send a string; JSON formats may send a string or an object.
    raw_log: str | dict[str, Any]


class ParseBatchRequest(BaseModel):
    """Items are parsed one by one, so one malformed log does not reject the rest."""

    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1, max_length=64)
    logs: list[Any] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class ParseResponse(BaseModel):
    success: bool = True
    message: str
    event: SecurityEvent


class ParseErrorItem(BaseModel):
    index: int  # position in `logs`, starting at 0
    code: str
    message: str
    field: str | None = None
    details: list[FieldError] = Field(default_factory=list)  # schema validation problems, if any


class ParseBatchResponse(BaseModel):
    success: bool  # True only when every log was accepted
    message: str
    total: int
    accepted: int
    rejected: int
    event_ids: list[str]
    errors: list[ParseErrorItem]
