import pytest
from pydantic import ValidationError

from app.repositories.alert_repository import AlertRepository
from app.repositories.base import DuplicateRecordError
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.repositories.initialization import initialize_database
from app.repositories.investigation_repository import InvestigationRepository
from tests.test_models import make_alert, make_event, make_rule


@pytest.fixture
def db(mongo_db):
    initialize_database(mongo_db)  # unique indexes must exist for duplicate checks
    return mongo_db


def test_event_create_and_find_by_id(db):
    repo = EventRepository(db)
    created = repo.create(make_event())
    found = repo.find_by_id("evt_001")
    assert found == created
    assert found.timestamp.tzinfo is not None  # timezone survives the round trip


def test_find_by_id_returns_none_when_missing(db):
    assert EventRepository(db).find_by_id("nope") is None


def test_duplicate_event_id_rejected(db):
    repo = EventRepository(db)
    repo.create(make_event())
    with pytest.raises(DuplicateRecordError):
        repo.create(make_event(message="different message"))


def test_find_many_filters_sorts_and_limits(db):
    repo = EventRepository(db)
    for i in range(5):
        repo.create(make_event(event_id=f"evt_{i}", timestamp=f"2026-10-02T10:15:0{i}Z",
                               status="failed" if i < 3 else "success"))
    failed = repo.find_many({"status": "failed"}, sort=[("timestamp", -1)])
    assert [e.event_id for e in failed] == ["evt_2", "evt_1", "evt_0"]
    assert len(repo.find_many(limit=2)) == 2


def test_find_many_rejects_bad_paging(db):
    repo = EventRepository(db)
    with pytest.raises(ValueError):
        repo.find_many(limit=0)
    with pytest.raises(ValueError):
        repo.find_many(skip=-1)


def test_alert_update_changes_status_and_updated_at(db):
    repo = AlertRepository(db)
    created = repo.create(make_alert())
    updated = repo.update("alert_001", {"status": "investigating"})
    assert updated.status == "investigating"
    assert updated.updated_at >= created.updated_at
    assert repo.find_by_id("alert_001").status == "investigating"


def test_update_rejects_invalid_value_and_keeps_stored_data(db):
    repo = AlertRepository(db)
    repo.create(make_alert())
    with pytest.raises(ValidationError):
        repo.update("alert_001", {"status": "banana"})
    assert repo.find_by_id("alert_001").status == "open"


def test_update_rejects_protected_fields_and_missing_records(db):
    repo = AlertRepository(db)
    repo.create(make_alert())
    with pytest.raises(ValueError):
        repo.update("alert_001", {"alert_id": "alert_999"})
    with pytest.raises(ValueError):
        repo.update("alert_001", {})
    assert repo.update("missing", {"status": "resolved"}) is None


def test_rule_round_trip_preserves_flexible_conditions(db):
    repo = DetectionRuleRepository(db)
    repo.create(make_rule())
    found = repo.find_by_id("AUTH-001")
    assert found.conditions == {"event_type": "authentication", "status": "failed", "threshold": 5, "window_minutes": 5}
    assert [r.rule_id for r in repo.find_many({"enabled": True})] == ["AUTH-001"]


def test_investigation_create_and_read(db):
    from app.models.investigation import Investigation

    repo = InvestigationRepository(db)
    repo.create(Investigation(investigation_id="inv_001", alert_ids=["alert_001"], title="Test"))
    assert repo.find_by_id("inv_001").title == "Test"
