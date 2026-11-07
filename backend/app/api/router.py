"""Aggregates all versioned API routers. Future routers (auth) are added here."""

from fastapi import APIRouter

from app.api.v1 import alerts, detection, events, health, investigations, parsing, rules

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(events.router)
api_router.include_router(parsing.router)
api_router.include_router(detection.router)
api_router.include_router(rules.router)
api_router.include_router(alerts.router)
api_router.include_router(investigations.router)
