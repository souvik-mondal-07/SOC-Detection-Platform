"""Request / response schemas for the rule-management API (Step 7).

Requests never accept timestamps: created_at / updated_at are set by the server.
Unknown fields are rejected, so rule_id cannot be changed through an update.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.models.common import RULE_ID_PATTERN, Severity
from app.models.rule import DetectionRule, RuleCategory

MAX_NAME = 120
MAX_DESCRIPTION = 1000


class RuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    name: str = Field(min_length=1, max_length=MAX_NAME)
    category: RuleCategory
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION)
    severity: Severity
    enabled: StrictBool = True
    conditions: dict[str, Any]  # content is validated by the service with the engine's own rules


class RuleUpdateRequest(BaseModel):
    """Partial update: send only the fields to change. rule_id is immutable."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    category: RuleCategory | None = None
    description: str | None = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION)
    severity: Severity | None = None
    enabled: StrictBool | None = None
    conditions: dict[str, Any] | None = None


class RuleStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class RuleSummary(BaseModel):
    rule_id: str
    name: str
    category: str
    severity: str
    enabled: bool


class RuleDetail(RuleSummary):
    description: str
    conditions: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_rule(cls, rule: DetectionRule) -> "RuleDetail":
        return cls(**rule.model_dump(mode="python"))


class RuleResponse(BaseModel):
    success: bool = True
    rule: RuleDetail


class RuleListResponse(BaseModel):
    success: bool = True
    page: int
    limit: int
    total: int  # rules matching the filters, across all pages
    count: int  # rules in this page
    rules: list[RuleSummary]


class RuleStatusResponse(BaseModel):
    success: bool = True
    rule_id: str
    enabled: bool


class RuleDeleteResponse(BaseModel):
    success: bool = True
    rule_id: str
    message: str = "Detection rule deleted"


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: str
    details: list[dict[str, str]] | None = None
