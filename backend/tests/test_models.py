from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.alert import Alert
from app.models.event import SecurityEvent
from app.models.investigation import Investigation
from app.models.rule import DetectionRule


def make_event(**overrides):
    data = dict(
        event_id="evt_001",
        timestamp="2026-10-02T10:15:23Z",
        source="linux_auth",
        event_type="authentication",
        action="login",
        status="failed",
        username="test_user",
        source_ip="192.168.1.20",
        message="Failed password for test_user",
    )
    return SecurityEvent(**{**data, **overrides})


def make_alert(**overrides):
    data = dict(
        alert_id="alert_001",
        rule_id="AUTH-001",
        title="Multiple Failed Logins",
        description="Multiple failed authentication attempts detected",
        severity="high",
        source_ip="192.168.1.20",
        event_ids=["evt_001", "evt_002"],
    )
    return Alert(**{**data, **overrides})


def make_rule(**overrides):
    data = dict(
        rule_id="AUTH-001",
        name="Multiple Failed Logins",
        category="authentication",
        description="Detect repeated failed authentication attempts",
        severity="high",
        conditions={"event_type": "authentication", "status": "failed", "threshold": 5, "window_minutes": 5},
    )
    return DetectionRule(**{**data, **overrides})


# ---- SecurityEvent ----

def test_valid_event_accepted_and_defaults_applied():
    event = make_event()
    assert event.timestamp == datetime(2026, 10, 2, 10, 15, 23, tzinfo=timezone.utc)
    assert event.metadata == {}
    assert event.created_at.tzinfo is not None
    assert event.to_document()["event_type"] == "authentication"  # stored as plain string


@pytest.mark.parametrize(
    "overrides",
    [
        {"event_id": "has spaces"},
        {"event_type": "unknown_type"},
        {"status": "maybe"},
        {"source_ip": "999.1.1.1"},
        {"timestamp": "2026-10-02T10:15:23"},  # no timezone
        {"timestamp": "not a date"},
        {"message": ""},
        {"unexpected_field": "x"},
    ],
)
def test_invalid_event_rejected(overrides):
    with pytest.raises(ValidationError):
        make_event(**overrides)


def test_event_timestamp_converted_to_utc():
    event = make_event(timestamp="2026-10-02T12:15:23+02:00")
    assert event.timestamp == datetime(2026, 10, 2, 10, 15, 23, tzinfo=timezone.utc)


def test_event_metadata_is_extensible():
    event = make_event(metadata={"http_status": 404, "nested": {"a": [1, 2]}})
    assert event.metadata["nested"]["a"] == [1, 2]


@pytest.mark.parametrize("bad_key", ["password", "user_Password", "api_token", "$where", "a.b"])
def test_event_metadata_rejects_secret_like_and_unsafe_keys(bad_key):
    with pytest.raises(ValidationError):
        make_event(metadata={bad_key: "x"})


# ---- Alert ----

@pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
def test_alert_valid_severity_accepted(severity):
    assert make_alert(severity=severity).severity == severity


@pytest.mark.parametrize("severity", ["urgent", "HIGH", "", "info"])
def test_alert_invalid_severity_rejected(severity):
    with pytest.raises(ValidationError):
        make_alert(severity=severity)


@pytest.mark.parametrize("status", ["open", "investigating", "resolved", "false_positive"])
def test_alert_valid_status_accepted(status):
    assert make_alert(status=status).status == status


@pytest.mark.parametrize("status", ["closed", "Open", "", "false positive"])
def test_alert_invalid_status_rejected(status):
    with pytest.raises(ValidationError):
        make_alert(status=status)


def test_alert_defaults_to_open():
    assert make_alert().status == "open"


def test_alert_requires_events_and_rejects_duplicates():
    with pytest.raises(ValidationError):
        make_alert(event_ids=[])
    with pytest.raises(ValidationError):
        make_alert(event_ids=["evt_001", "evt_001"])


def test_alert_updated_at_cannot_precede_created_at():
    with pytest.raises(ValidationError):
        make_alert(created_at="2026-10-02T10:20:00Z", updated_at="2026-10-02T10:00:00Z")


# ---- DetectionRule ----

def test_valid_rule_accepted():
    rule = make_rule()
    assert rule.enabled is True
    assert rule.conditions["threshold"] == 5


def test_rule_conditions_are_flexible():
    rule = make_rule(conditions={"stages": [{"status": "failed", "min_count": 5}], "window_minutes": 10})
    assert rule.conditions["stages"][0]["min_count"] == 5


@pytest.mark.parametrize(
    "overrides",
    [
        {"rule_id": "auth001"},
        {"category": "made_up"},
        {"severity": "urgent"},
        {"conditions": {}},
        {"conditions": {"$where": "1"}},
        {"enabled": "maybe"},
        {"name": ""},
    ],
)
def test_invalid_rule_rejected(overrides):
    with pytest.raises(ValidationError):
        make_rule(**overrides)


# ---- Investigation ----

def test_investigation_defaults_and_notes():
    inv = Investigation(investigation_id="inv_001", alert_ids=["alert_001"], title="Authentication Activity Investigation")
    assert inv.status == "open" and inv.notes == []


def test_investigation_invalid_values_rejected():
    with pytest.raises(ValidationError):
        Investigation(investigation_id="inv_001", alert_ids=[], title="x")
    with pytest.raises(ValidationError):
        Investigation(investigation_id="inv_001", alert_ids=["alert_001"], title="x", status="done")
