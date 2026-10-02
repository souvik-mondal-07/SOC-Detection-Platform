"""Detection rule definition (stored data only; evaluation comes in a later step)."""

from enum import Enum
from typing import Any, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from app.models.common import (
    RULE_ID_PATTERN,
    MongoModel,
    Severity,
    UTCDateTime,
    check_mongo_safe_keys,
    utc_now,
)


class RuleCategory(str, Enum):
    AUTHENTICATION = "authentication"
    WEB = "web"
    NETWORK = "network"
    PRIVILEGE = "privilege"
    CORRELATION = "correlation"


class DetectionRule(MongoModel):
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    category: RuleCategory
    description: str = Field(min_length=1, max_length=1000)
    severity: Severity
    enabled: StrictBool = True
    # Deliberately free-form: the detection engine (a later step) decides how to
    # interpret it. It must only be non-empty and safe to store in MongoDB.
    conditions: dict[str, Any]
    created_at: UTCDateTime = Field(default_factory=utc_now)
    updated_at: UTCDateTime = Field(default_factory=utc_now)

    @field_validator("conditions")
    @classmethod
    def _conditions_valid(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("conditions must not be empty")
        return check_mongo_safe_keys(value)

    @model_validator(mode="after")
    def _updated_not_before_created(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self
