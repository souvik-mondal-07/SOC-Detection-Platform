"""Event ingestion: validate -> normalise -> build the stored event -> save.

This service only stores events. It deliberately knows nothing about rules,
thresholds or alerts: detection will be a separate module that reads stored
events. Database access goes through EventRepository only.
"""

import secrets
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from app.core.errors import summarize_validation_errors
from app.models.common import utc_now
from app.models.event import (
    BatchIngestResponse,
    BatchItemError,
    EventCreate,
    EventQuery,
    FieldError,
    SecurityEvent,
)
from app.repositories.event_repository import EventRepository


class EventNotFoundError(Exception):
    pass


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def generate_event_id() -> str:
    """Random, non-sequential ID: 'evt_' + 16 hex characters (64 random bits)."""
    return f"evt_{secrets.token_hex(8)}"


class EventIngestionService:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    # -- ingestion ---------------------------------------------------------

    def ingest_event(self, event: EventCreate) -> SecurityEvent:
        """Store one already-validated, already-normalised incoming event."""
        return self._repository.create_event(self._to_stored_event(event))

    def ingest_many(self, events: Sequence[EventCreate]) -> list[SecurityEvent]:
        """Store already-validated events with one insert. Used by the parsing service."""
        stored = [self._to_stored_event(event) for event in events]
        self._repository.create_many(stored)
        return stored

    def ingest_batch(self, raw_events: Sequence[Any]) -> BatchIngestResponse:
        """Validate each item on its own. Valid events are stored; invalid ones are
        reported by position and do not affect the others."""
        stored: list[SecurityEvent] = []
        errors: list[BatchItemError] = []

        for index, raw in enumerate(raw_events):
            if not isinstance(raw, dict):
                errors.append(BatchItemError(index=index, errors=[FieldError(field="(event)", message="Each event must be a JSON object")]))
                continue
            try:
                stored.append(self._to_stored_event(EventCreate.model_validate(raw)))
            except ValidationError as exc:
                details = [FieldError(**item) for item in summarize_validation_errors(exc.errors())]
                errors.append(BatchItemError(index=index, errors=details))

        accepted = self._repository.create_many(stored)
        rejected = len(errors)
        if rejected == 0:
            message = f"{_count(accepted, 'security event')} ingested successfully"
        elif accepted == 0:
            message = f"No events ingested: {_count(rejected, 'event')} rejected"
        else:
            message = f"{_count(accepted, 'event')} ingested, {rejected} rejected"
        return BatchIngestResponse(
            success=rejected == 0,
            message=message,
            accepted=accepted,
            rejected=rejected,
            event_ids=[event.event_id for event in stored],
            errors=errors,
        )

    # -- retrieval (read-only) --------------------------------------------

    def get_event(self, event_id: str) -> SecurityEvent:
        event = self._repository.get_event_by_id(event_id)
        if event is None:
            raise EventNotFoundError(event_id)
        return event

    def list_events(self, query: EventQuery) -> list[SecurityEvent]:
        return self._repository.get_events(**query.model_dump(exclude_none=True))

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _to_stored_event(event: EventCreate) -> SecurityEvent:
        now = utc_now()
        data = event.model_dump()
        metadata = dict(data["metadata"])
        if data["timestamp"] is None:
            # No timestamp supplied: use ingestion time and mark it, so later
            # analysis can tell it apart from a timestamp reported by the source.
            data["timestamp"] = now
            metadata["timestamp_generated"] = True
        data["metadata"] = metadata
        return SecurityEvent(event_id=generate_event_id(), created_at=now, **data)
