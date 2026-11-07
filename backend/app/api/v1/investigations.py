"""Investigation endpoints (/api/v1/investigations).

NO AUTHENTICATION YET: these endpoints are for the local development environment only. Routes translate
HTTP to InvestigationService calls. Investigation status is independent of alert status, and nothing here
changes an alert's status, severity or priority.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pymongo.database import Database

from app.core.database import get_database
from app.models.common import ID_PATTERN
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_management import (
    InvestigationCreateRequest,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationUpdateRequest,
    LinkAlertsRequest,
    NoteCreateRequest,
    to_detail,
    to_list_item,
)
from app.repositories.alert_repository import AlertRepository
from app.repositories.investigation_repository import MAX_INVESTIGATION_PAGE_LIMIT, InvestigationRepository
from app.services.investigation_service import InvestigationService, InvestigationServiceError

router = APIRouter(prefix="/investigations", tags=["investigations"])

DEFAULT_PAGE_LIMIT = 20

InvestigationId = Annotated[str, Path(min_length=1, max_length=64, pattern=ID_PATTERN)]
AlertIdPath = Annotated[str, Path(min_length=1, max_length=64, pattern=ID_PATTERN)]


def get_investigation_service(database: Database = Depends(get_database)) -> InvestigationService:
    return InvestigationService(InvestigationRepository(database), AlertRepository(database))


ServiceDep = Annotated[InvestigationService, Depends(get_investigation_service)]


def _http_error(exc: InvestigationServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _response(service: InvestigationService, investigation: Investigation) -> InvestigationResponse:
    return InvestigationResponse(investigation=to_detail(investigation, service.linked_alerts(investigation)))


@router.get("", response_model=InvestigationListResponse)
def list_investigations(
    service: ServiceDep,
    status: InvestigationStatus | None = None,
    alert_id: Annotated[str | None, Query(pattern=ID_PATTERN, max_length=64)] = None,
    title: Annotated[str | None, Query(min_length=1, max_length=100, description="Case-insensitive title search")] = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_INVESTIGATION_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
) -> InvestigationListResponse:
    """List investigations, newest first. Filter by status, by a linked alert_id, or by a title substring."""
    items, total = service.list_investigations(
        status=status.value if status else None, alert_id=alert_id, title_contains=title.strip() if title else None, page=page, limit=limit
    )
    return InvestigationListResponse(page=page, limit=limit, total=total, count=len(items), investigations=[to_list_item(i) for i in items])


@router.post("", response_model=InvestigationResponse, status_code=201)
def create_investigation(payload: InvestigationCreateRequest, service: ServiceDep) -> InvestigationResponse:
    """Create an investigation for one or more existing alerts. Alerts that do not exist are rejected, never created."""
    try:
        return _response(service, service.create(payload.title, payload.alert_ids))
    except InvestigationServiceError as exc:
        raise _http_error(exc) from None


@router.get("/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(investigation_id: InvestigationId, service: ServiceDep) -> InvestigationResponse:
    try:
        return _response(service, service.get(investigation_id))
    except InvestigationServiceError as exc:
        raise _http_error(exc) from None


@router.patch("/{investigation_id}", response_model=InvestigationResponse)
def update_investigation(investigation_id: InvestigationId, payload: InvestigationUpdateRequest, service: ServiceDep) -> InvestigationResponse:
    """Change the title and/or the investigation status (open, in_progress, closed). Invalid transitions return 409."""
    try:
        status = payload.status.value if payload.status else None
        return _response(service, service.update(investigation_id, title=payload.title, status=status))
    except InvestigationServiceError as exc:
        raise _http_error(exc) from None


@router.post("/{investigation_id}/alerts", response_model=InvestigationResponse)
def link_alerts(investigation_id: InvestigationId, payload: LinkAlertsRequest, service: ServiceDep) -> InvestigationResponse:
    """Link existing alerts. Unknown alerts return 404 and already-linked alerts return 409; nothing is linked in either case."""
    try:
        return _response(service, service.link_alerts(investigation_id, payload.alert_ids))
    except InvestigationServiceError as exc:
        raise _http_error(exc) from None


@router.delete("/{investigation_id}/alerts/{alert_id}", response_model=InvestigationResponse)
def unlink_alert(investigation_id: InvestigationId, alert_id: AlertIdPath, service: ServiceDep) -> InvestigationResponse:
    """Remove the link only. The alert itself is untouched. The last remaining alert cannot be unlinked (409)."""
    try:
        return _response(service, service.unlink_alert(investigation_id, alert_id))
    except InvestigationServiceError as exc:
        raise _http_error(exc) from None


@router.post("/{investigation_id}/notes", response_model=InvestigationResponse, status_code=201)
def add_note(investigation_id: InvestigationId, payload: NoteCreateRequest, service: ServiceDep) -> InvestigationResponse:
    """Append a note (1-2000 characters). Notes are append-only; the response holds the full investigation, notes oldest first."""
    try:
        return _response(service, service.add_note(investigation_id, payload.text))
    except InvestigationServiceError as exc:
        raise _http_error(exc) from None
