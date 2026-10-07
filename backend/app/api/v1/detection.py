"""Detection endpoints. Routes translate HTTP to service calls only. They return
detection results and never create alerts."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pymongo.database import Database

from app.core.database import get_database
from app.models.common import ID_PATTERN
from app.models.detection import (
    BatchEvaluationResponse,
    DetectionBatchRequest,
    EventEvaluationResponse,
    EventMatches,
)
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.services.detection_service import DetectionService
from app.services.ingestion_service import EventNotFoundError

router = APIRouter(prefix="/detection", tags=["detection"])


def get_detection_service(database: Database = Depends(get_database)) -> DetectionService:
    return DetectionService(EventRepository(database), DetectionRuleRepository(database))


ServiceDep = Annotated[DetectionService, Depends(get_detection_service)]


@router.post("/evaluate/{event_id}", response_model=EventEvaluationResponse)
def evaluate_event(service: ServiceDep, event_id: str = Path(min_length=1, max_length=64, pattern=ID_PATTERN)) -> EventEvaluationResponse:
    """Run all enabled rules against one stored event and return the rules that matched."""
    try:
        detection = service.evaluate_event_id(event_id)
    except EventNotFoundError:
        raise HTTPException(status_code=404, detail="Event not found") from None
    return EventEvaluationResponse(
        event_id=detection.event_id,
        matches=detection.matches,
        rules_evaluated=detection.rules_evaluated,
        skipped_rule_ids=detection.skipped_rule_ids,
    )


@router.post("/evaluate", response_model=BatchEvaluationResponse)
def evaluate_events(payload: DetectionBatchRequest, service: ServiceDep) -> BatchEvaluationResponse:
    """Evaluate up to 500 stored events. Unknown event IDs are listed, not treated as errors."""
    batch = service.evaluate_event_ids(payload.event_ids)
    skipped = sorted({rule_id for d in batch.detections for rule_id in d.skipped_rule_ids})
    return BatchEvaluationResponse(
        events_evaluated=len(batch.detections),
        total_matches=batch.total_matches,
        results=[EventMatches(event_id=d.event_id, matches=d.matches) for d in batch.detections],
        not_found_event_ids=batch.not_found_event_ids,
        skipped_rule_ids=skipped,
    )
