"""Centralised error handling so every error returns the same JSON shape:
{"error": {"message": "...", "details": [...optional...]}}.

Responses never include stack traces, connection strings, file paths or the
values the client sent.
"""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("soc.errors")


class DatabaseUnavailableError(Exception):
    """Raised when MongoDB cannot be reached. Carries no connection details."""


class DuplicateRecordError(Exception):
    """A record with the same unique identifier already exists."""


def summarize_validation_errors(errors: Sequence[Any]) -> list[dict[str, str]]:
    """Reduce Pydantic errors to {field, message}. The submitted values are
    deliberately left out so secrets in a rejected request are never echoed."""
    summary = []
    for error in errors:
        field = ".".join(str(part) for part in error.get("loc", ())) or "(event)"
        summary.append({"field": field, "message": str(error.get("msg", "Invalid value"))})
    return summary


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"message": "Validation failed", "details": summarize_validation_errors(exc.errors())}},
        )

    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable_handler(_: Request, __: DatabaseUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": {"message": "Database is unavailable"}})

    @app.exception_handler(DuplicateRecordError)
    async def duplicate_record_handler(_: Request, __: DuplicateRecordError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": {"message": "Record already exists"}})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal server error"}},
        )
