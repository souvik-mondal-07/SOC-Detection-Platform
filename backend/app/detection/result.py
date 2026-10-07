"""Structured detection results. A result says whether a rule matched; it is not an alert."""

from typing import Any

from pydantic import BaseModel, Field

from app.models.common import Severity


class DetectionResult(BaseModel):
    matched: bool
    rule_id: str
    rule_name: str | None = None
    category: str | None = None
    event_id: str
    reason: str
    severity: Severity | None = None  # set only when the rule matched
    # IDs of the events that made the rule match (capped), useful input for later alerting.
    matched_event_ids: list[str] = Field(default_factory=list)
    # Counts, window and correlation value behind the decision.
    details: dict[str, Any] = Field(default_factory=dict)


class EventDetection(BaseModel):
    """Everything the engine decided for one event."""

    event_id: str
    results: list[DetectionResult] = Field(default_factory=list)  # one per evaluated rule, matched or not
    rules_evaluated: int = 0
    skipped_rule_ids: list[str] = Field(default_factory=list)  # rules with invalid conditions

    @property
    def matches(self) -> list[DetectionResult]:
        return [result for result in self.results if result.matched]


class BatchDetection(BaseModel):
    detections: list[EventDetection] = Field(default_factory=list)
    not_found_event_ids: list[str] = Field(default_factory=list)

    @property
    def total_matches(self) -> int:
        return sum(len(detection.matches) for detection in self.detections)
