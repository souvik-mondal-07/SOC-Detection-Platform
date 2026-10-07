"""Request / response schemas for the detection API."""

import re

from pydantic import BaseModel, ConfigDict, Field

from app.detection.result import DetectionResult
from app.models.common import ID_PATTERN

MAX_EVALUATE_BATCH = 500
_ID = re.compile(ID_PATTERN)


class DetectionBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_ids: list[str] = Field(min_length=1, max_length=MAX_EVALUATE_BATCH)

    def model_post_init(self, _context) -> None:
        if not all(_ID.match(item) for item in self.event_ids):
            raise ValueError("event_ids must contain valid event IDs")


class EventEvaluationResponse(BaseModel):
    success: bool = True
    event_id: str
    matches: list[DetectionResult]  # only rules that matched
    rules_evaluated: int
    skipped_rule_ids: list[str] = Field(default_factory=list)  # rules with invalid conditions


class EventMatches(BaseModel):
    event_id: str
    matches: list[DetectionResult]


class BatchEvaluationResponse(BaseModel):
    success: bool = True
    events_evaluated: int
    total_matches: int
    results: list[EventMatches]  # one entry per evaluated event
    not_found_event_ids: list[str] = Field(default_factory=list)
    skipped_rule_ids: list[str] = Field(default_factory=list)
