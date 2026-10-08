"""Fixtures for alert tests: synthetic events plus the real initial rules in mongomock."""

import importlib.util
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pytest

from app.models.event import SecurityEvent
from app.repositories.alert_repository import AlertRepository
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.repositories.initialization import initialize_database
from app.services.alert_service import AlertService

SEED_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "seed_detection_rules.py"
T0 = datetime(2026, 10, 2, 10, 0, 0, tzinfo=timezone.utc)
_ids = count(1)


def make(seconds: float = 0, **overrides) -> SecurityEvent:
    """A failed Linux login from 192.168.1.20 by default."""
    data = dict(
        event_id=f"evt_{next(_ids):05d}", timestamp=T0 + timedelta(seconds=seconds), source="linux_auth",
        event_type="authentication", action="login", status="failed", username="test_user",
        source_ip="192.168.1.20", message="Failed password",
    )
    return SecurityEvent(**{**data, **overrides})


@pytest.fixture(scope="session")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed_detection_rules", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db(mongo_db, seed_module):
    initialize_database(mongo_db)
    repo = DetectionRuleRepository(mongo_db)
    for rule in seed_module.build_rules():
        repo.save_rule(rule)
    return mongo_db


@pytest.fixture
def event_repo(db):
    return EventRepository(db)


@pytest.fixture
def alert_repo(db):
    return AlertRepository(db)


@pytest.fixture
def rule_repo(db):
    return DetectionRuleRepository(db)


@pytest.fixture
def service(alert_repo, rule_repo, event_repo):
    return AlertService(alert_repo, rule_repo, event_repo)


@pytest.fixture
def burst(event_repo):
    """Five failed logins from one IP inside a minute (triggers AUTH-001)."""
    events = [make(i * 10) for i in range(5)]
    event_repo.create_many(events)
    return events


@pytest.fixture
def normal_event(event_repo):
    event = make(0, status="success", username="alice", source_ip="10.0.0.5", message="Accepted password")
    event_repo.create_event(event)
    return event
