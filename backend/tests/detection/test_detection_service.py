"""Service + repositories: rule loading, repository queries, seed script."""

import pytest

from app.detection.base import InvalidRuleError
from app.models.rule import DetectionRule
from app.repositories.event_repository import build_match_query
from app.services.detection_service import DetectionService
from app.services.ingestion_service import EventNotFoundError
from tests.detection.conftest import at, make, store


@pytest.fixture
def service(event_repo, rule_repo):
    return DetectionService(event_repo, rule_repo)


@pytest.fixture
def seeded(seed_module, mongo_db):
    seed_module.seed(mongo_db)
    return mongo_db


def test_service_evaluates_with_enabled_rules_from_mongodb(service, event_repo, seeded):
    events = store(event_repo, [make(i * 5) for i in range(5)])
    detection = service.evaluate_event_id(events[-1].event_id)
    assert [m.rule_id for m in detection.matches] == ["AUTH-001"]
    assert detection.rules_evaluated == 5


def test_service_ignores_disabled_rules(service, event_repo, rule_repo, seeded):
    rule_repo.update("AUTH-001", {"enabled": False})
    events = store(event_repo, [make(i * 5) for i in range(5)])
    detection = service.evaluate_event_id(events[-1].event_id)
    assert detection.matches == [] and detection.rules_evaluated == 4


def test_service_unknown_event_raises(service, seeded):
    with pytest.raises(EventNotFoundError):
        service.evaluate_event_id("evt_missing")


def test_service_with_no_rules_returns_no_results(service, event_repo):
    event = store(event_repo, [make(0)])[0]
    detection = service.evaluate_event_id(event.event_id)
    assert detection.results == [] and detection.rules_evaluated == 0


def test_batch_evaluation_counts_and_reports_unknown_ids(service, event_repo, seeded):
    events = store(event_repo, [make(i * 5) for i in range(5)])
    ids = [e.event_id for e in events] + [events[0].event_id, "evt_missing"]  # a duplicate and an unknown ID
    batch = service.evaluate_event_ids(ids)
    assert len(batch.detections) == 5 and batch.not_found_event_ids == ["evt_missing"]
    assert batch.total_matches == 5  # every event of the burst matches AUTH-001


def test_corrupt_stored_rule_is_skipped_by_the_repository(rule_repo, mongo_db, seeded):
    mongo_db["detection_rules"].insert_one({"rule_id": "AUTH-777", "name": "x", "category": "bogus", "severity": "huge",
                                            "enabled": True, "conditions": {"a": 1}})
    ids = [r.rule_id for r in rule_repo.get_enabled_rules()]
    assert "AUTH-777" not in ids and "AUTH-001" in ids


# ---------------------------------------------------------------- rule repository

def test_save_rule_creates_then_updates_without_duplicates(rule_repo, seed_module):
    rule = seed_module.build_rules()[0]
    saved, created = rule_repo.save_rule(rule)
    assert created
    changed = rule.model_copy(update={"severity": "critical"})
    updated, created = rule_repo.save_rule(changed)
    assert not created and updated.severity == "critical"
    assert len(rule_repo.list_rules()) == 1
    assert updated.created_at == saved.created_at


def test_save_rule_keeps_operator_disabled_flag(rule_repo, seed_module):
    rule = seed_module.build_rules()[0]
    rule_repo.save_rule(rule)
    rule_repo.update(rule.rule_id, {"enabled": False})
    kept, _ = rule_repo.save_rule(rule)
    assert kept.enabled is False
    assert rule_repo.get_enabled_rules() == []


def test_repository_lookup_and_listing(rule_repo, seed_module):
    for rule in seed_module.build_rules():
        rule_repo.save_rule(rule)
    assert rule_repo.get_rule("WEB-001").category == "web"
    assert rule_repo.get_rule("NOPE-001") is None
    assert [r.rule_id for r in rule_repo.list_rules(category="authentication")] == ["AUTH-001", "AUTH-002", "AUTH-003"]
    assert len(rule_repo.get_enabled_rules()) == 5


# ---------------------------------------------------------------- seed script

def test_seed_creates_five_valid_rules_and_is_idempotent(seed_module, mongo_db):
    first = seed_module.seed(mongo_db)
    assert first == {rid: "created" for rid in ("AUTH-001", "AUTH-002", "AUTH-003", "WEB-001", "NET-001")}
    second = seed_module.seed(mongo_db)
    assert set(second.values()) == {"updated"}
    assert mongo_db["detection_rules"].count_documents({}) == 5
    assert mongo_db["alerts"].count_documents({}) == 0  # rule seeding never touches alerts


def test_seed_updates_the_step3_sample_rule_in_place(seed_module, mongo_db):
    """seed_database.py (Step 3) stored AUTH-002 with a different meaning; re-seeding replaces its definition."""
    from app.repositories.detection_rule_repository import DetectionRuleRepository
    from app.repositories.initialization import initialize_database

    initialize_database(mongo_db)
    legacy = DetectionRule(rule_id="AUTH-002", name="Old", category="authentication", severity="critical",
                           description="Step 3 sample", conditions={"window_minutes": 10, "stages": [{"status": "failed"}]})
    DetectionRuleRepository(mongo_db).create(legacy)
    seed_module.seed(mongo_db)
    rule = DetectionRuleRepository(mongo_db).get_rule("AUTH-002")
    assert rule.name == "Invalid User Login Attempt" and rule.severity == "medium"
    assert mongo_db["detection_rules"].count_documents({"rule_id": "AUTH-002"}) == 1


def test_seed_rules_do_not_run_on_startup():
    from pathlib import Path
    main = (Path(__file__).resolve().parents[2] / "app" / "main.py").read_text()
    assert "seed" not in main.lower() and "build_rules" not in main


# ---------------------------------------------------------------- event repository queries

def test_count_and_find_use_filters_and_time_range(event_repo):
    store(event_repo, [make(0), make(60), make(120, status="success"), make(180, source_ip="10.0.0.9"),
                       make(240, event_type="web", source="web_application", action="http_request")])
    kwargs = dict(event_type="authentication", status="failed", source_ip="192.168.1.20")
    assert event_repo.count_matching_events(**kwargs) == 2
    assert event_repo.count_matching_events(**kwargs, start=at(30)) == 1
    assert event_repo.count_matching_events(**kwargs, start=at(0), end=at(60)) == 2  # bounds are inclusive
    assert event_repo.count_matching_events(**kwargs, end=at(59)) == 1
    found = event_repo.find_matching_events(**kwargs)
    assert [e.timestamp for e in found] == [at(0), at(60)]  # oldest first
    assert len(event_repo.find_matching_events(event_type="authentication", limit=2)) == 2


def test_query_filters_cover_action_source_username_and_metadata(event_repo):
    store(event_repo, [make(0, metadata={"reason": "invalid_user"}, username="ghost"), make(1, action="logout"),
                       make(2, source="windows_event"), make(3, username=None)])
    assert event_repo.count_matching_events(metadata={"reason": "invalid_user"}) == 1
    assert event_repo.count_matching_events(metadata={"reason": ["invalid_user", "other"]}) == 1
    assert event_repo.count_matching_events(action="logout") == 1
    assert event_repo.count_matching_events(source="windows_event") == 1
    assert event_repo.count_matching_events(username="ghost") == 1
    assert event_repo.count_matching_events(username_present=True) == 3
    assert event_repo.count_matching_events() == 4


def test_match_query_rejects_operator_injection():
    for bad in ({"$where": 1}, {"a.b": 1}, {"reason": {"$ne": 1}}, {"reason": []}, {"reason": [{"$gt": 1}]}):
        with pytest.raises(ValueError):
            build_match_query(metadata=bad)


def test_find_limit_is_bounded(event_repo):
    with pytest.raises(ValueError):
        event_repo.find_matching_events(limit=0)
    with pytest.raises(ValueError):
        event_repo.find_matching_events(limit=10**6)


def test_detection_indexes_exist(event_repo, mongo_db):
    names = set(mongo_db["security_events"].index_information())
    assert {"ix_detection_type_status_ip_timestamp", "ix_detection_type_status_user_timestamp"} <= names


def test_batch_fetch_by_ids(event_repo):
    events = store(event_repo, [make(0), make(1)])
    assert {e.event_id for e in event_repo.get_events_by_ids([events[0].event_id, "evt_x"])} == {events[0].event_id}
    assert event_repo.get_events_by_ids([]) == []
