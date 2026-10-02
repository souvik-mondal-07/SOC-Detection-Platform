"""Optional tests against a REAL MongoDB. Skipped unless explicitly enabled.

Run (PowerShell, MongoDB running locally):
    $env:RUN_MONGO_INTEGRATION = "1"; python -m pytest tests/test_mongo_integration.py

Uses a throwaway database named soc_test_<random> and drops ONLY that database
afterwards. It never touches the configured application database.
"""

import os
import uuid

import pytest
from pymongo import MongoClient

from app.core.config import get_settings
from app.core.database import check_connection
from app.repositories.base import DuplicateRecordError
from app.repositories.event_repository import EventRepository
from app.repositories.initialization import initialize_database
from tests.test_models import make_event

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MONGO_INTEGRATION") != "1", reason="set RUN_MONGO_INTEGRATION=1 to run"
)


@pytest.fixture
def real_db():
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True)
    name = f"soc_test_{uuid.uuid4().hex[:8]}"
    database = client[name]
    try:
        yield database
    finally:
        assert name.startswith("soc_test_")  # safety: only ever drop our own temp database
        client.drop_database(name)
        client.close()


def test_real_mongodb_is_reachable(real_db):
    assert check_connection(real_db) is True


def test_real_mongodb_indexes_and_unique_ids(real_db):
    initialize_database(real_db)
    repo = EventRepository(real_db)
    repo.create(make_event())
    with pytest.raises(DuplicateRecordError):
        repo.create(make_event())
    found = repo.find_by_id("evt_001")
    assert found.timestamp.tzinfo is not None
    assert "uq_event_id" in real_db["security_events"].index_information()
