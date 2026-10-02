"""Shared building blocks for all MongoDB document models."""

import ipaddress
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict

# Identifier formats. Rule IDs look like AUTH-001; other IDs like evt_001.
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
RULE_ID_PATTERN = r"^[A-Z]{2,10}-\d{3,}$"
SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"

# Metadata must never carry credentials. Keys containing these words are rejected.
_SECRET_KEY_WORDS = ("password", "passwd", "secret", "token", "api_key", "apikey", "private_key")


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def utc_now() -> datetime:
    """Current UTC time, truncated to milliseconds (MongoDB's datetime precision)."""
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone, e.g. 2026-10-02T10:15:23Z")
    return value.astimezone(timezone.utc)


def _validate_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise ValueError("must be a valid IPv4 or IPv6 address") from exc


def _ensure_unique(values: list[str]) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError("list must not contain duplicates")
    return values


def check_mongo_safe_keys(value: Any, *, forbid_secrets: bool = False) -> Any:
    """Reject keys MongoDB treats specially ("$..." or containing ".") at any depth.

    With forbid_secrets=True also reject keys that look like credentials.
    Only keys are inspected; values are never read or echoed in errors.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("keys must be non-empty strings")
            if key.startswith("$") or "." in key:
                raise ValueError(f"key {key!r} may not start with '$' or contain '.'")
            if forbid_secrets and any(word in key.lower() for word in _SECRET_KEY_WORDS):
                raise ValueError(f"key {key!r} looks like a credential; do not store secrets")
            check_mongo_safe_keys(child, forbid_secrets=forbid_secrets)
    elif isinstance(value, list):
        for child in value:
            check_mongo_safe_keys(child, forbid_secrets=forbid_secrets)
    return value


# Reusable annotated types
UTCDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]
IPAddressStr = Annotated[str, AfterValidator(_validate_ip)]
UniqueIdList = Annotated[list[str], AfterValidator(_ensure_unique)]


class MongoModel(BaseModel):
    """Base class: unknown fields are rejected and enums are stored as plain strings."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        validate_default=True,
        str_strip_whitespace=True,
    )

    def to_document(self) -> dict[str, Any]:
        """Plain dict ready for MongoDB."""
        return self.model_dump(mode="python")

    @classmethod
    def from_document(cls, document: dict[str, Any]):
        """Build a model from a MongoDB document, ignoring Mongo's internal _id."""
        return cls.model_validate({k: v for k, v in document.items() if k != "_id"})
