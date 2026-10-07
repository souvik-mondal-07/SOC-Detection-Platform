"""Event endpoints. Routes only translate HTTP to service calls; there are no
database queries and no detection logic here."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pymongo.database import Database

from app.core.database import get_database
from app.models.event import (
    BatchEventRequest,
    BatchIngestResponse,
    EventCreate,
    EventIngestResponse,
    EventListResponse,
    EventQuery,
    SecurityEvent,
)
from app.repositories.event_repository import EventRepository
from app.services.ingestion_service import EventIngestionService, EventNotFoundError

router = APIRouter(prefix="/events", tags=["events"])


def get_ingestion_service(database: Database = Depends(get_database)) -> EventIngestionService:
    return EventIngestionService(EventRepository(database))


ServiceDep = Annotated[EventIngestionService, Depends(get_ingestion_service)]


@router.post("", status_code=201, response_model=EventIngestResponse)
def ingest_event(payload: EventCreate, service: ServiceDep) -> EventIngestResponse:
    """Validate, normalise and store one security event."""
    event = service.ingest_event(payload)
    return EventIngestResponse(message="Security event ingested successfully", event=event)


@router.post("/batch", status_code=201, response_model=BatchIngestResponse)
def ingest_batch(payload: BatchEventRequest, service: ServiceDep, response: Response) -> BatchIngestResponse:
    """Store up to 500 events. Valid events are stored even if others are rejected (HTTP 201).
    If every event is rejected nothing is stored and the status is 422."""
    result = service.ingest_batch(payload.events)
    if result.accepted == 0:
        response.status_code = 422
    return result


@router.get("", response_model=EventListResponse)
def list_events(query: Annotated[EventQuery, Query()], service: ServiceDep) -> EventListResponse:
    """Recent events, newest first, with optional exact-match filters."""
    events = service.list_events(query)
    return EventListResponse(count=len(events), events=events)


@router.get("/{event_id}", response_model=SecurityEvent)
def get_event(service: ServiceDep, event_id: str = Path(min_length=1, max_length=64)) -> SecurityEvent:
    try:
        return service.get_event(event_id)
    except EventNotFoundError:
        raise HTTPException(status_code=404, detail="Event not found") from None
