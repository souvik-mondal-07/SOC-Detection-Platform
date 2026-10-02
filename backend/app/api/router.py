"""Aggregates all versioned API routers. Future routers (events, alerts, rules, auth) are added here."""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
