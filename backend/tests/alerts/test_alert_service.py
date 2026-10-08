import pytest

from app.core.errors import DatabaseUnavailableError
from app.detection.result import DetectionResult
from app.models.common import utc_now
from app.services.alert_service import InvalidDetectionResultError, RuleNotFoundForAlertError
from app.services.ingestion_service import EventNotFoundError
from tests.alerts.conftest import make  # noqa: F401  (rootdir on path via pytest.ini)


def test_matching_event_creates_alert(service, burst):
    outcome = service.generate_for_event_id(burst[-1].event_id)
    assert len(outcome.created) == 1
    alert = outcome.created[0]
    assert alert.rule_id == "AUTH-001" and alert.title == "Multiple Failed Logins Detected"
    assert alert.severity == "high" and alert.status == "open" and alert.source_ip == "192.168.1.20"
    assert set(alert.event_ids) == {e.event_id for e in burst}
    assert alert.alert_id == f"ALT-{utc_now():%Y%m%d}-000001"
    assert "requires investigation" in alert.description.lower() and "5 minutes" in alert.description
    assert alert.created_at == alert.updated_at


def test_non_matching_event_creates_nothing(service, normal_event, alert_repo):
    outcome = service.generate_for_event_id(normal_event.event_id)
    assert outcome.created == [] and alert_repo.get_alerts()[1] == 0


def test_severity_comes_from_rule_not_event(service, event_repo, rule_repo):
    event = make(0, metadata={"severity": "critical", "http_status": 500}, message="Failed password")
    event_repo.create_event(event)
    rule_repo.update_rule("AUTH-002", {"severity": "low"})
    invalid = make(5, metadata={"reason": "invalid_user", "severity": "critical"})
    event_repo.create_event(invalid)
    outcome = service.generate_for_event_id(invalid.event_id)
    assert [a.severity for a in outcome.created if a.rule_id == "AUTH-002"] == ["low"]


def test_result_severity_is_ignored(service, rule_repo, burst):
    result = DetectionResult(matched=True, rule_id="AUTH-001", event_id=burst[0].event_id, reason="r",
                             severity="low", matched_event_ids=[e.event_id for e in burst])
    assert service.create_alert_from_result(result, burst[0]).severity == "high"


def test_duplicates_controlled(service, burst, alert_repo):
    service.generate_for_event_id(burst[-1].event_id)
    again = service.generate_for_event_id(burst[-1].event_id)
    other_event = service.generate_for_event_id(burst[0].event_id)  # same burst, different trigger
    assert again.created == [] and again.duplicates_skipped == 1
    assert other_event.created == [] and alert_repo.get_alerts()[1] == 1


def test_new_alert_after_original_leaves_open_state(service, burst, alert_repo):
    first = service.generate_for_event_id(burst[-1].event_id).created[0]
    alert_repo.update_alert(first.alert_id, {"status": "resolved"})
    second = service.generate_for_event_id(burst[-1].event_id).created
    assert len(second) == 1 and second[0].alert_id.endswith("-000002")


def test_missing_event(service):
    with pytest.raises(EventNotFoundError):
        service.generate_for_event_id("evt_missing")


def test_missing_rule(service, burst, rule_repo):
    result = DetectionResult(matched=True, rule_id="GONE-001", event_id=burst[0].event_id, reason="r")
    with pytest.raises(RuleNotFoundForAlertError):
        service.create_alert_from_result(result)


def test_invalid_detection_result(service, rule_repo):
    result = DetectionResult(matched=True, rule_id="AUTH-001", event_id="evt 1!", reason="r")
    with pytest.raises(InvalidDetectionResultError):
        service.create_alert_from_result(result)


def test_unmatched_result_returns_none(service):
    assert service.create_alert_from_result(DetectionResult(matched=False, rule_id="AUTH-001", event_id="e", reason="r")) is None


def test_source_ip_not_invented(service, event_repo):
    event = make(0, source_ip=None, metadata={"reason": "invalid_user"})
    event_repo.create_event(event)
    alert = service.generate_for_event_id(event.event_id).created[0]
    assert alert.rule_id == "AUTH-002" and alert.source_ip is None


def test_batch_continues_after_failure(service, burst, normal_event):
    outcome = service.generate_for_event_ids([burst[-1].event_id, "evt_missing", normal_event.event_id])
    assert outcome.events_evaluated == 2 and len(outcome.created) == 1
    assert outcome.failures == [("evt_missing", "EVENT_NOT_FOUND", "Event not found")]


def test_database_failure_propagates(service, burst, monkeypatch):
    def boom(*_a, **_k):
        raise DatabaseUnavailableError("down")
    monkeypatch.setattr(service._alerts, "create_alert", boom)
    with pytest.raises(DatabaseUnavailableError):
        service.generate_for_event_id(burst[-1].event_id)
