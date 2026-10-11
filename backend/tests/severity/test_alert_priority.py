"""Priority on real generated alerts (rules and events are synthetic, DB is mongomock)."""

from datetime import timedelta

import pytest

from app.models.alert import Alert
from app.models.common import utc_now
from app.models.rule import DetectionRule
from app.repositories.detection_rule_repository import DetectionRuleRepository
from tests.alerts.conftest import make


def add_rule(db, rule_id, severity):
    DetectionRuleRepository(db).save_rule(DetectionRule(
        rule_id=rule_id, name=f"Synthetic {severity}", category="system", severity=severity,
        description="synthetic test rule", conditions={"event_type": "system", "status": "failed"},
    ))


def system_event(event_repo, **kw):
    event = make(0, event_type="system", action="service_start", source_ip=kw.pop("source_ip", "10.9.9.9"), **kw)
    event_repo.create_event(event)
    return event


def test_scenario_a_low(db, service, event_repo):
    add_rule(db, "TEST-001", "low")
    alerts = service.generate_for_event_id(system_event(event_repo).event_id).created
    assert len(alerts) == 1 and alerts[0].severity == "low" and alerts[0].priority_score == 25
    assert alerts[0].priority_reason == "Low severity rule"


def test_scenario_b_medium_above_low(db, service, event_repo):
    add_rule(db, "TEST-002", "medium")
    (alert,) = service.generate_for_event_id(system_event(event_repo).event_id).created
    assert alert.severity == "medium" and alert.priority_score >= 50 > 25


def test_scenario_c_auth001_high(service, burst):
    (alert,) = service.generate_for_event_id(burst[-1].event_id).created
    assert alert.rule_id == "AUTH-001" and alert.severity == "high"
    assert alert.priority_score == 83 and alert.priority_reason == "High severity rule with multiple correlated events"
    assert alert.priority_score - 50 >= 25  # significantly above a medium baseline


def test_scenario_c_recent_burst_gets_recency_boost(service, event_repo):
    now = utc_now()
    events = [make(0, timestamp=now - timedelta(seconds=10 * i)) for i in range(5)]
    event_repo.create_many(events)
    (alert,) = service.generate_for_event_id(events[0].event_id).created
    assert alert.priority_score == 86 and alert.priority_reason.endswith("and recent activity")


def test_scenario_d_critical_synthetic_rule(db, service, event_repo):
    add_rule(db, "TEST-009", "critical")
    (alert,) = service.generate_for_event_id(system_event(event_repo, timestamp=utc_now()).event_id).created
    assert alert.severity == "critical" and alert.priority_score == 100 and alert.priority_score <= 100


def test_event_supplied_severity_cannot_change_alert(service, event_repo):
    events = [make(i * 10, metadata={"severity": "critical", "priority_score": 100}) for i in range(5)]
    event_repo.create_many(events)
    (alert,) = service.generate_for_event_id(events[-1].event_id).created
    assert alert.severity == "high" and alert.priority_score == 83


def test_priority_is_persisted(service, alert_repo, burst):
    (alert,) = service.generate_for_event_id(burst[-1].event_id).created
    document = alert_repo._collection.find_one({"alert_id": alert.alert_id}, {"_id": 0})
    assert document["priority_score"] == 83 and document["priority_reason"]


def test_legacy_alert_without_priority_gets_base_score(alert_repo):
    alert_repo._collection.insert_one({
        "alert_id": "ALT-20260101-000001", "rule_id": "AUTH-001", "title": "t", "description": "d", "severity": "medium",
        "status": "open", "source_ip": None, "event_ids": ["evt_1"], "created_at": utc_now(), "updated_at": utc_now(),
    })
    alert = alert_repo.get_alert_by_id("ALT-20260101-000001")
    assert alert.priority_score == 50 and alert.priority_reason is None


@pytest.mark.parametrize("score", [-1, 101])
def test_model_rejects_out_of_range_score(score):
    with pytest.raises(ValueError):
        Alert(alert_id="ALT-1", rule_id="AUTH-001", title="t", description="d", severity="high",
              priority_score=score, event_ids=["e"])
