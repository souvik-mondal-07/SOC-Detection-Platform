"""FastAPI application entry point."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import close_client, get_database
from app.core.errors import DatabaseUnavailableError, register_exception_handlers
from app.repositories.initialization import initialize_database

logger = logging.getLogger("soc.startup")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Best effort and non-destructive: creates missing collections/indexes only.
    # If MongoDB is down the app still starts and /health reports "degraded".
    try:
        await asyncio.to_thread(lambda: initialize_database(get_database()))
        logger.info("Database initialized")
    except (DatabaseUnavailableError, PyMongoError) as exc:
        logger.warning("Database initialization skipped (%s)", type(exc).__name__)
    yield
    close_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
