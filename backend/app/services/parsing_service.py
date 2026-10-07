"""Raw log -> parser -> EventCreate (validation + normalization) -> ingestion service.

This service contains no detection logic: it never counts events, applies
thresholds or creates alerts. Database access stays in the ingestion service.
"""

from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from app.core.errors import summarize_validation_errors
from app.models.event import EventCreate, FieldError, SecurityEvent
from app.models.parsing import ParseBatchResponse, ParseErrorItem
from app.parsers.base import ParseError
from app.parsers.registry import ParserRegistry, UnsupportedParserError, default_registry
from app.services.ingestion_service import EventIngestionService

__all__ = ["LogParseError", "ParsingService", "UnsupportedParserError"]


class LogParseError(Exception):
    """A single log could not be parsed or did not produce a valid event."""

    def __init__(self, code: str, message: str, field: str | None = None, details: list[FieldError] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.details = details or []


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


class ParsingService:
    def __init__(self, ingestion: EventIngestionService, registry: ParserRegistry | None = None) -> None:
        self._ingestion = ingestion
        self._registry = registry or default_registry()

    def parse_and_ingest(self, source_type: str, raw_log: Any) -> SecurityEvent:
        """Raises UnsupportedParserError or LogParseError; database errors propagate unchanged."""
        parser = self._registry.get_parser(source_type)
        return self._ingestion.ingest_event(self._build_event(parser, raw_log))

    def parse_batch(self, source_type: str, logs: Sequence[Any]) -> ParseBatchResponse:
        parser = self._registry.get_parser(source_type)  # unsupported type fails the whole request
        events: list[EventCreate] = []
        errors: list[ParseErrorItem] = []
        for index, raw_log in enumerate(logs):
            try:
                events.append(self._build_event(parser, raw_log))
            except LogParseError as exc:
                errors.append(ParseErrorItem(index=index, code=exc.code, message=exc.message, field=exc.field, details=exc.details))

        stored = self._ingestion.ingest_many(events) if events else []
        accepted, rejected = len(stored), len(errors)
        if rejected == 0:
            message = f"{_count(accepted, 'log')} parsed and ingested successfully"
        elif accepted == 0:
            message = f"No events ingested: {_count(rejected, 'log')} rejected"
        else:
            message = f"{_count(accepted, 'log')} ingested, {rejected} rejected"
        return ParseBatchResponse(
            success=rejected == 0,
            message=message,
            total=len(logs),
            accepted=accepted,
            rejected=rejected,
            event_ids=[event.event_id for event in stored],
            errors=errors,
        )

    @staticmethod
    def _build_event(parser, raw_log: Any) -> EventCreate:
        try:
            parsed = parser.parse(raw_log)
        except ParseError as exc:
            raise LogParseError(exc.code, exc.message, exc.field) from None
        except Exception:  # a parser bug must not take down a batch or leak internals
            raise LogParseError("parser_error", "The log could not be parsed") from None
        try:
            return EventCreate.model_validate(parsed)
        except ValidationError as exc:
            details = [FieldError(**item) for item in summarize_validation_errors(exc.errors())]
            raise LogParseError("validation_failed", "Parsed data is not a valid security event", details=details) from None
