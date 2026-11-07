"""Fixtures for investigation tests: real alerts stored in mongomock (no mocked alert data)."""

from itertools import count

import pytest

from app.models.alert import Alert
from app.repositories.alert_repository import AlertRepository
from app.repositories.initialization import initialize_database
from app.repositories.investigation_repository import InvestigationRepository
from app.services.investigation_service import InvestigationService

_numbers = count(1)


def build_alert(**overrides) -> Alert:
    n = next(_numbers)
    data = dict(
        alert_id=f"ALT-20261014-{n:06d}", rule_id="AUTH-001", title="Multiple Failed Logins Detected",
        description="Five failed logins in one minute", severity="high", priority_score=83, status="open",
        source_ip="192.168.1.20", event_ids=[f"evt_{n:05d}", f"evt_{n + 1000:05d}"],
    )
    return Alert(**{**data, **overrides})


@pytest.fixture
def db(mongo_db):
    initialize_database(mongo_db)
    return mongo_db


@pytest.fixture
def alert_repo(db):
    return AlertRepository(db)


@pytest.fixture
def investigation_repo(db):
    return InvestigationRepository(db)


@pytest.fixture
def service(investigation_repo, alert_repo):
    return InvestigationService(investigation_repo, alert_repo)


@pytest.fixture
def alerts(alert_repo):
    """Three stored alerts with different severities."""
    return [
        alert_repo.create_alert(build_alert(severity="critical", priority_score=95, source_ip="10.0.0.9")),
        alert_repo.create_alert(build_alert(severity="medium", priority_score=50, source_ip=None)),
        alert_repo.create_alert(build_alert(severity="low", priority_score=20)),
    ]


@pytest.fixture
def investigation(client, db, alerts):
    """One investigation linked to the first alert, created through the API."""
    r = client.post("/api/v1/investigations", json={"title": "Brute force from 10.0.0.9", "alert_ids": [alerts[0].alert_id]})
    assert r.status_code == 201
    return r.json()["investigation"]
