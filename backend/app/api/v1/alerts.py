"""Alert endpoints (/api/v1/alerts). Routes translate HTTP to AlertService /
AlertRepository calls. Alerts are only ever created by running detection
server-side; clients cannot supply alert_id, severity, status or timestamps."""

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pymongo.database import Database

from app.core.database import get_database
from app.core.severity import MAX_PRIORITY_SCORE, MIN_PRIORITY_SCORE
from app.models.alert import AlertStatus
from app.models.alert_management import (
    AlertGenerationResponse,
    AlertListResponse,
    AlertResponse,
    AlertStatsResponse,
    AlertStatusUpdateRequest,
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
    priority_min: Annotated[int | None, Query(ge=MIN_PRIORITY_SCORE, le=MAX_PRIORITY_SCORE)] = None,
    priority_max: Annotated[int | None, Query(ge=MIN_PRIORITY_SCORE, le=MAX_PRIORITY_SCORE)] = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_ALERT_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
) -> AlertListResponse:
    """List alerts, highest priority first (ties: newest first). Filtering, sorting and pagination happen in MongoDB."""
    if priority_min is not None and priority_max is not None and priority_min > priority_max:
        raise HTTPException(status_code=422, detail="priority_min cannot be greater than priority_max")
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
        priority_min=priority_min,
        priority_max=priority_max,
        skip=(page - 1) * limit,
        limit=limit,
    )
    return AlertListResponse(page=page, limit=limit, total=total, count=len(alerts), alerts=[to_list_item(a) for a in alerts])


@router.get("/stats", response_model=AlertStatsResponse)
def alert_stats(repository: RepositoryDep) -> AlertStatsResponse:
    """Exact lifecycle and severity counts across all alerts. Declared before /{alert_id} so "stats" is not read as an ID."""
    return AlertStatsResponse(**repository.get_stats())


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(repository: RepositoryDep, alert_id: str = Path(min_length=1, max_length=64, pattern=ID_PATTERN)) -> AlertResponse:
    alert = repository.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse(alert=to_detail(alert))


AlertIdPath = Annotated[str, Path(min_length=1, max_length=64, pattern=ID_PATTERN)]


def _lifecycle_error(exc: AlertServiceError) -> HTTPException:
    return HTTPException(status_code=getattr(exc, "status_code", 409), detail=exc.message)


# NO AUTHENTICATION YET: the two routes below change alert state and are for local development only.
@router.patch("/{alert_id}/status", response_model=AlertResponse)
def update_alert_status(alert_id: AlertIdPath, payload: AlertStatusUpdateRequest, service: ServiceDep) -> AlertResponse:
    """Move an alert through its lifecycle (investigating, resolved, false_positive, or back to open).

    404 unknown alert, 409 disallowed transition or concurrent change, 422 invalid status or missing reason.
    """
    try:
        alert = service.change_status(alert_id, payload.status, payload.reason)
    except AlertServiceError as exc:
        raise _lifecycle_error(exc) from None
    return AlertResponse(alert=to_detail(alert))


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(alert_id: AlertIdPath, service: ServiceDep) -> AlertResponse:
    """Acknowledge an open alert. The status stays `open`; acknowledged_at and a history entry are recorded."""
    try:
        alert = service.acknowledge(alert_id)
    except AlertServiceError as exc:
        raise _lifecycle_error(exc) from None
    return AlertResponse(alert=to_detail(alert))
