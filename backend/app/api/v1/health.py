"""Health-check endpoint."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo.database import Database

from app.core.config import get_settings
from app.core.database import check_connection, get_database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    message: str
    service: str
    version: str
    environment: str
    database: Literal["connected", "unavailable"]
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
def health_check(database: Database = Depends(get_database)) -> HealthResponse:
    """Always answers 200 so the API itself stays reachable. If MongoDB is down,
    status is "degraded" and database is "unavailable" (no connection details shown)."""
    settings = get_settings()
    connected = check_connection(database)
    return HealthResponse(
        status="ok" if connected else "degraded",
        message="Backend is running" if connected else "Backend is running; database is unavailable",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="connected" if connected else "unavailable",
        timestamp=datetime.now(timezone.utc),
    )
