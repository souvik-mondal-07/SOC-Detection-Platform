"""Normalised security event."""

from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from app.models.common import (
    ID_PATTERN,
    SNAKE_CASE_PATTERN,
    IPAddressStr,
    MongoModel,
    UTCDateTime,
    check_mongo_safe_keys,
    utc_now,
)


class EventType(str, Enum):
    AUTHENTICATION = "authentication"
    WEB = "web"
    NETWORK = "network"
    PRIVILEGE = "privilege"


class EventStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SecurityEvent(MongoModel):
    event_id: str = Field(pattern=ID_PATTERN)
    timestamp: UTCDateTime
    source: str = Field(pattern=SNAKE_CASE_PATTERN)
    event_type: EventType
    action: str = Field(pattern=SNAKE_CASE_PATTERN)
    status: EventStatus
    username: str | None = Field(default=None, min_length=1, max_length=64)
    source_ip: IPAddressStr | None = None
    message: str = Field(min_length=1, max_length=1000)
    # Extensible, source-specific extras. Credential-like keys are rejected.
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: UTCDateTime = Field(default_factory=utc_now)

    @field_validator("metadata")
    @classmethod
    def _metadata_is_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        return check_mongo_safe_keys(value, forbid_secrets=True)
