"""Centralised error handling so every error returns the same JSON shape."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("soc.errors")


class DatabaseUnavailableError(Exception):
    """Raised when MongoDB cannot be reached. Carries no connection details."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})

    @app.exception_handler(DatabaseUnavailableError)
    async def database_unavailable_handler(_: Request, __: DatabaseUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": {"message": "Database is unavailable"}})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal server error"}},
        )
