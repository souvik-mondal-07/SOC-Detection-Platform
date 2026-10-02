"""Shared fixtures. Tests use an in-memory MongoDB stand-in (mongomock), never a real database."""

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.core.database import get_database
from app.main import app


@pytest.fixture
def mongo_db():
    return mongomock.MongoClient(tz_aware=True)["soc_test"]


@pytest.fixture
def client(mongo_db):
    app.dependency_overrides[get_database] = lambda: mongo_db
    yield TestClient(app)
    app.dependency_overrides.clear()
