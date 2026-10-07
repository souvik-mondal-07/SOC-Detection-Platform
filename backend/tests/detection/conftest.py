"""Helpers for detection tests: synthetic events and the real initial rules."""

import importlib.util
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pytest

from app.detection.engine import DetectionEngine
from app.detection.rule_evaluator import RuleEvaluator
from app.models.event import SecurityEvent
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.repositories.initialization import initialize_database

SEED_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "seed_detection_rules.py"
T0 = datetime(2026, 10, 2, 10, 0, 0, tzinfo=timezone.utc)
_ids = count(1)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def make(seconds: float = 0, **overrides) -> SecurityEvent:
    """A failed Linux login by default; override any field."""
    data = dict(
        event_id=f"evt_{next(_ids):05d}", timestamp=at(seconds), source="linux_auth", event_type="authentication",
        action="login", status="failed", username="test_user", source_ip="192.168.1.20", message="Failed password",
    )
    return SecurityEvent(**{**data, **overrides})


def web(seconds: float, http_status: int = 404, **kw) -> SecurityEvent:
    base = dict(source="web_application", event_type="web", action="http_request", username=None,
                status="failed", message=f"GET /x {http_status}", metadata={"http_status": http_status})
    return make(seconds, **{**base, **kw})


def net(seconds: float, port: int, **kw) -> SecurityEvent:
    base = dict(source="network", event_type="network", action="connection", username=None, status="success",
                message=f"Connection to port {port}", metadata={"destination_port": port})
    return make(seconds, **{**base, **kw})


@pytest.fixture(scope="session")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed_detection_rules", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rules(seed_module):
    return {rule.rule_id: rule for rule in seed_module.build_rules()}


@pytest.fixture
def event_repo(mongo_db):
    initialize_database(mongo_db)
    return EventRepository(mongo_db)


@pytest.fixture
def rule_repo(mongo_db):
    initialize_database(mongo_db)
    return DetectionRuleRepository(mongo_db)


@pytest.fixture
def evaluator(event_repo):
    return RuleEvaluator(event_repo)


@pytest.fixture
def engine(evaluator):
    return DetectionEngine(evaluator)


def store(repo: EventRepository, events: list[SecurityEvent]) -> list[SecurityEvent]:
    repo.create_many(events)
    return events
