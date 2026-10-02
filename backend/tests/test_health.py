from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.database import get_database
from app.main import app


def test_health_check_returns_ok_when_database_connected(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["message"] == "Backend is running"
    assert {"service", "version", "environment", "timestamp"} <= body.keys()


def test_health_reports_degraded_when_database_unavailable():
    # Real driver pointed at a closed local port, with a short timeout.
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    app.dependency_overrides[get_database] = lambda: dead["soc_test"]
    try:
        response = TestClient(app).get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
        dead.close()
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert "127.0.0.1" not in response.text and "mongodb://" not in response.text


def test_unknown_route_returns_json_error():
    response = TestClient(app).get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "error" in response.json()


def test_cors_allows_local_frontend(client):
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
