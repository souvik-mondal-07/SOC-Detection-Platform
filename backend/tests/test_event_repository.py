import ast
from pathlib import Path

import pytest

from app.models.event import SecurityEvent
from app.repositories.event_repository import EventRepository
from app.repositories.initialization import initialize_database
from tests.test_models import make_event

APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture
def repo(mongo_db):
    initialize_database(mongo_db)
    return EventRepository(mongo_db)


def test_create_event_and_get_event_by_id(repo):
    repo.create_event(make_event(event_id="evt_a"))
    assert repo.get_event_by_id("evt_a").event_id == "evt_a"
    assert repo.get_event_by_id("missing") is None


def test_create_many_inserts_all_and_handles_empty(repo):
    assert repo.create_many([]) == 0
    assert repo.create_many([make_event(event_id=f"evt_{i}") for i in range(4)]) == 4
    assert len(repo.get_events()) == 4


def test_get_events_filters_sort_and_limit(repo):
    repo.create_many([
        make_event(event_id="evt_1", timestamp="2026-10-02T10:00:00Z", status="failed", source_ip="192.168.1.20"),
        make_event(event_id="evt_2", timestamp="2026-10-02T10:01:00Z", status="success", source_ip="192.168.1.20"),
        make_event(event_id="evt_3", timestamp="2026-10-02T10:02:00Z", status="failed", source="network", event_type="network", source_ip="192.168.1.60"),
    ])
    assert [e.event_id for e in repo.get_events()] == ["evt_3", "evt_2", "evt_1"]
    assert [e.event_id for e in repo.get_events(status="failed")] == ["evt_3", "evt_1"]
    assert [e.event_id for e in repo.get_events(source="network")] == ["evt_3"]
    assert [e.event_id for e in repo.get_events(event_type="network", status="failed")] == ["evt_3"]
    assert [e.event_id for e in repo.get_events(source_ip="192.168.1.20", limit=1)] == ["evt_2"]


def test_get_events_accepts_enum_members(repo):
    from app.models.event import EventStatus

    repo.create_event(make_event(event_id="evt_1", status="blocked"))
    assert len(repo.get_events(status=EventStatus.BLOCKED)) == 1


def test_filter_indexes_exist(mongo_db, repo):
    names = set(mongo_db["security_events"].index_information())
    assert {"ix_source_timestamp", "ix_status_timestamp", "ix_event_type_timestamp", "ix_source_ip_timestamp"} <= names


def test_legacy_stored_source_remains_readable(repo, mongo_db):
    """Documents written before Step 4 (e.g. source 'audit_log') must not break reads."""
    mongo_db["security_events"].insert_one(make_event(event_id="evt_old", source="audit_log").to_document())
    assert repo.get_event_by_id("evt_old").source == "audit_log"


def test_ingestion_code_has_no_detection_or_alert_dependencies():
    """Architecture rule: ingestion stores events only; detection is a separate module."""
    forbidden = ("alert", "rule", "detection", "investigation")
    for path in (APP_DIR / "services" / "ingestion_service.py", APP_DIR / "api" / "v1" / "events.py"):
        tree = ast.parse(path.read_text())
        imported = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imported += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not [m for m in imported if any(word in m for word in forbidden)], path.name


def test_routes_contain_no_database_calls():
    source = (APP_DIR / "api" / "v1" / "events.py").read_text()
    assert "pymongo" not in source.replace("from pymongo.database import Database", "")
    assert ".find(" not in source and "insert_" not in source
