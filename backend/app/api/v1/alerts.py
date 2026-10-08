"""Alert endpoints (/api/v1/alerts). Routes translate HTTP to AlertService /
AlertRepository calls. Alerts are only ever created by running detection
server-side; clients cannot supply alert_id, severity, status or timestamps."""

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pymongo.database import Database

from app.core.database import get_database
from app.models.alert import AlertStatus
from app.models.alert_management import (
    AlertGenerationResponse,
    AlertListResponse,
    AlertResponse,
    BatchAlertGenerationResponse,
    FailedEvent,
    to_detail,
    to_list_item,
    to_summary,
)
from app.models.common import ID_PATTERN, RULE_ID_PATTERN, Severity
from app.models.detection import DetectionBatchRequest
from app.repositories.alert_repository import MAX_ALERT_PAGE_LIMIT, AlertRepository
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.services.alert_service import AlertService, AlertServiceError
from app.services.ingestion_service import EventNotFoundError

router = APIRouter(prefix="/alerts", tags=["alerts"])

DEFAULT_PAGE_LIMIT = 20


def get_alert_repository(database: Database = Depends(get_database)) -> AlertRepository:
    return AlertRepository(database)


def get_alert_service(database: Database = Depends(get_database)) -> AlertService:
    return AlertService(AlertRepository(database), DetectionRuleRepository(database), EventRepository(database))


ServiceDep = Annotated[AlertService, Depends(get_alert_service)]
RepositoryDep = Annotated[AlertRepository, Depends(get_alert_repository)]


@router.post("/generate/{event_id}", response_model=AlertGenerationResponse)
def generate_alerts_for_event(
    service: ServiceDep, event_id: str = Path(min_length=1, max_length=64, pattern=ID_PATTERN)
) -> AlertGenerationResponse:
    """Run detection on one stored event and persist an alert for each matching rule."""
    try:
        outcome = service.generate_for_event_id(event_id)
    except EventNotFoundError:
        raise HTTPException(status_code=404, detail="Event not found") from None
    except AlertServiceError as exc:
        raise HTTPException(status_code=422 if exc.error_code == "INVALID_DETECTION_RESULT" else 409, detail=exc.message) from None
    return AlertGenerationResponse(
        event_id=event_id,
        alerts_created=len(outcome.created),
        duplicates_skipped=outcome.duplicates_skipped,
        alerts=[to_summary(alert) for alert in outcome.created],
    )


@router.post("/generate", response_model=BatchAlertGenerationResponse)
def generate_alerts_batch(payload: DetectionBatchRequest, service: ServiceDep) -> BatchAlertGenerationResponse:
    """Evaluate several events. Failed events are reported in `failed_events`; the rest are processed."""
    outcome = service.generate_for_event_ids(payload.event_ids)
    return BatchAlertGenerationResponse(
        events_evaluated=outcome.events_evaluated,
        alerts_created=len(outcome.created),
        duplicates_skipped=outcome.duplicates_skipped,
        alerts=[to_summary(alert) for alert in outcome.created],
        failed_events=[FailedEvent(event_id=i, error_code=c, message=m) for i, c, m in outcome.failures],
    )


@router.get("", response_model=AlertListResponse)
def list_alerts(
    repository: RepositoryDep,
    status: AlertStatus | None = None,
    severity: Severity | None = None,
    rule_id: Annotated[str | None, Query(pattern=RULE_ID_PATTERN, max_length=32)] = None,
    source_ip: Annotated[str | None, Query(max_length=45)] = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_ALERT_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
) -> AlertListResponse:
    """List alerts, newest first. Filtering and pagination happen in MongoDB."""
    if source_ip is not None:
        try:
            source_ip = str(ipaddress.ip_address(source_ip))
        except ValueError:
            raise HTTPException(status_code=422, detail="source_ip must be a valid IP address") from None
    alerts, total = repository.get_alerts(
        status=status.value if status else None,
        severity=severity.value if severity else None,
        rule_id=rule_id,
        source_ip=source_ip,
        skip=(page - 1) * limit,
        limit=limit,
    )
    return AlertListResponse(page=page, limit=limit, total=total, count=len(alerts), alerts=[to_list_item(a) for a in alerts])


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(repository: RepositoryDep, alert_id: str = Path(min_length=1, max_length=64, pattern=ID_PATTERN)) -> AlertResponse:
    alert = repository.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse(alert=to_detail(alert))
