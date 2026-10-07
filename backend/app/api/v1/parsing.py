"""Log-parsing endpoints. Routes only translate HTTP to service calls; parsing
lives in app/parsers and orchestration in ParsingService."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pymongo.database import Database

from app.core.database import get_database
from app.models.parsing import ParseBatchRequest, ParseBatchResponse, ParseRequest, ParseResponse
from app.repositories.event_repository import EventRepository
from app.services.ingestion_service import EventIngestionService
from app.services.parsing_service import LogParseError, ParsingService, UnsupportedParserError

router = APIRouter(prefix="/events/parse", tags=["parsing"])


def get_parsing_service(database: Database = Depends(get_database)) -> ParsingService:
    return ParsingService(EventIngestionService(EventRepository(database)))


ServiceDep = Annotated[ParsingService, Depends(get_parsing_service)]


def _unsupported(exc: UnsupportedParserError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": {
        "message": f"Unsupported source_type '{exc.source_type}'. Supported: {', '.join(exc.supported)}",
        "code": "unsupported_source_type",
    }})


@router.post("", status_code=201, response_model=ParseResponse, responses={400: {}, 422: {}})
def parse_log(payload: ParseRequest, service: ServiceDep):
    """Parse one raw log, normalise it and store it as a security event."""
    try:
        event = service.parse_and_ingest(payload.source_type, payload.raw_log)
    except UnsupportedParserError as exc:
        return _unsupported(exc)
    except LogParseError as exc:
        error = {"message": exc.message, "code": exc.code}
        if exc.field:
            error["field"] = exc.field
        if exc.details:
            error["details"] = [detail.model_dump() for detail in exc.details]
        return JSONResponse(status_code=422, content={"error": error})
    return ParseResponse(message="Log parsed and security event ingested successfully", event=event)


@router.post("/batch", status_code=201, response_model=ParseBatchResponse, responses={400: {}})
def parse_batch(payload: ParseBatchRequest, service: ServiceDep, response: Response):
    """Parse up to 500 logs of one type. Valid logs are stored even if others are rejected (HTTP 201).
    If every log is rejected nothing is stored and the status is 422."""
    try:
        result = service.parse_batch(payload.source_type, payload.logs)
    except UnsupportedParserError as exc:
        return _unsupported(exc)
    if result.accepted == 0:
        response.status_code = 422
    return result
