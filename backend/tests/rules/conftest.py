"""Fixtures for rule-management tests (in-memory MongoDB via the shared mongo_db fixture)."""

import importlib.util
from pathlib import Path

import pytest

from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.initialization import initialize_database
from app.services.rule_service import RuleService

SEED_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "seed_detection_rules.py"


@pytest.fixture(scope="session")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed_detection_rules", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(mongo_db):
    initialize_database(mongo_db)
    return DetectionRuleRepository(mongo_db)


@pytest.fixture
def service(repo):
    return RuleService(repo)


@pytest.fixture
def seeded(seed_module, mongo_db):
    seed_module.seed(mongo_db)
    return mongo_db


def rule_payload(**overrides) -> dict:
    data = {
        "rule_id": "AUTH-004",
        "name": "Repeated Authentication Failures",
        "category": "authentication",
        "description": "Detect repeated authentication failures",
        "severity": "high",
        "enabled": True,
        "conditions": {
            "event_type": "authentication", "status": "failed",
            "threshold": 10, "window_minutes": 10, "correlation_field": "source_ip",
        },
    }
    return {**data, **overrides}
