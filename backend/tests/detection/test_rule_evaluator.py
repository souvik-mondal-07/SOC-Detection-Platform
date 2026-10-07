"""Rule evaluation per rule: AUTH-002 (stateless), AUTH-003 (sequence), WEB-001, NET-001, safety."""

import pytest

from app.detection.base import InvalidRuleError
from app.models.rule import DetectionRule
from tests.detection.conftest import make, net, store, web


def rule_with(base: DetectionRule, **changes) -> DetectionRule:
    return DetectionRule(**{**base.model_dump(), **changes})


# ---------------------------------------------------------------- AUTH-002 (stateless)

def test_auth002_invalid_user_matches(evaluator, rules):
    event = make(metadata={"reason": "invalid_user"}, username="ghost")
    result = evaluator.evaluate(rules["AUTH-002"], event)
    assert result.matched and result.severity == "medium" and result.rule_id == "AUTH-002"
    assert result.matched_event_ids == [event.event_id]


def test_auth002_normal_successful_user_does_not_match(evaluator, rules):
    result = evaluator.evaluate(rules["AUTH-002"], make(status="success", message="Accepted password"))
    assert not result.matched and result.severity is None
    assert result.reason == "Event did not satisfy rule conditions"


def test_auth002_ordinary_failure_and_other_reason_do_not_match(evaluator, rules):
    assert not evaluator.evaluate(rules["AUTH-002"], make()).matched  # no metadata at all
    assert not evaluator.evaluate(rules["AUTH-002"], make(metadata={"reason": "pam_authentication_failure"})).matched
    # A message that merely contains the words must not match: only the parser's metadata counts.
    assert not evaluator.evaluate(rules["AUTH-002"], make(message="Invalid user ghost from 1.2.3.4")).matched


# ---------------------------------------------------------------- AUTH-003 (sequence)

def test_auth003_failures_then_success_matches(evaluator, event_repo, rules):
    failures = [make(s) for s in (0, 30, 60)]
    success = make(120, status="success", message="Accepted password")
    store(event_repo, [*failures, success])
    result = evaluator.evaluate(rules["AUTH-003"], success)
    assert result.matched and result.severity == "high"
    assert result.matched_event_ids == [*(f.event_id for f in failures), success.event_id]
    assert "preceded by 3 failed authentication events" in result.reason


def test_auth003_success_without_failures_does_not_match(evaluator, event_repo, rules):
    success = make(0, status="success")
    store(event_repo, [success])
    assert not evaluator.evaluate(rules["AUTH-003"], success).matched


def test_auth003_too_few_failures_does_not_match(evaluator, event_repo, rules):
    success = make(120, status="success")
    store(event_repo, [make(0), make(30), success])
    assert not evaluator.evaluate(rules["AUTH-003"], success).matched


def test_auth003_failures_outside_window_do_not_match(evaluator, event_repo, rules):
    success = make(1000, status="success")  # window is 10 minutes = 600 s
    store(event_repo, [make(0), make(10), make(20), success])
    assert not evaluator.evaluate(rules["AUTH-003"], success).matched


def test_auth003_failures_after_the_success_do_not_count(evaluator, event_repo, rules):
    success = make(0, status="success")
    store(event_repo, [success, make(10), make(20), make(30)])
    assert not evaluator.evaluate(rules["AUTH-003"], success).matched


def test_auth003_failures_from_another_ip_do_not_count(evaluator, event_repo, rules):
    success = make(120, status="success")
    store(event_repo, [make(0, source_ip="10.0.0.9"), make(10, source_ip="10.0.0.9"), make(20, source_ip="10.0.0.9"), success])
    assert not evaluator.evaluate(rules["AUTH-003"], success).matched


def test_auth003_evaluating_a_failure_event_does_not_match(evaluator, event_repo, rules):
    events = store(event_repo, [make(0), make(10), make(20), make(30)])
    assert not evaluator.evaluate(rules["AUTH-003"], events[-1]).matched  # the success event triggers it


# ---------------------------------------------------------------- WEB-001

def test_web001_below_threshold_no_match(evaluator, event_repo, rules):
    events = store(event_repo, [web(i * 10) for i in range(9)])
    assert not evaluator.evaluate(rules["WEB-001"], events[-1]).matched


def test_web001_threshold_reached_matches_with_mixed_403_404(evaluator, event_repo, rules):
    events = store(event_repo, [web(i * 10, http_status=403 if i % 2 else 404) for i in range(10)])
    result = evaluator.evaluate(rules["WEB-001"], events[-1])
    assert result.matched and result.severity == "medium"
    assert "http_status in [403, 404]" in result.reason


def test_web001_other_status_codes_do_not_count(evaluator, event_repo, rules):
    events = store(event_repo, [web(i * 10, http_status=404) for i in range(9)] + [web(95, http_status=500)])
    assert not evaluator.evaluate(rules["WEB-001"], events[-1]).matched  # a 500 is not a 403/404
    assert not evaluator.evaluate(rules["WEB-001"], events[0]).matched  # only 9 qualifying events


# ---------------------------------------------------------------- NET-001

def test_net001_fewer_unique_ports_no_match(evaluator, event_repo, rules):
    events = store(event_repo, [net(i * 5, 1000 + i) for i in range(9)])
    assert not evaluator.evaluate(rules["NET-001"], events[-1]).matched


def test_net001_threshold_reached_matches(evaluator, event_repo, rules):
    events = store(event_repo, [net(i * 5, 1000 + i) for i in range(10)])
    result = evaluator.evaluate(rules["NET-001"], events[0])
    assert result.matched and result.severity == "medium"
    assert result.details["observed"] == 10
    assert "10 distinct metadata.destination_port values" in result.reason


def test_net001_duplicate_ports_do_not_inflate_unique_count(evaluator, event_repo, rules):
    # 30 connections, but only 9 different ports.
    events = store(event_repo, [net(i * 2, 2000 + (i % 9)) for i in range(30)])
    result = evaluator.evaluate(rules["NET-001"], events[-1])
    assert not result.matched and result.details["observed"] == 9


# ---------------------------------------------------------------- safety

def test_disabled_rule_never_matches(evaluator, event_repo, rules):
    disabled = rule_with(rules["AUTH-002"], enabled=False)
    result = evaluator.evaluate(disabled, make(metadata={"reason": "invalid_user"}))
    assert not result.matched and result.reason == "Rule is disabled"


def test_event_without_correlation_field_fails_safely(evaluator, event_repo, rules):
    events = store(event_repo, [make(i, source_ip=None) for i in range(6)])
    result = evaluator.evaluate(rules["AUTH-001"], events[-1])
    assert not result.matched and "no source IP" in result.reason


def test_event_without_distinct_field_fails_safely(evaluator, event_repo, rules):
    event = store(event_repo, [net(0, 1)])[0]
    event_no_port = make(1, source="network", event_type="network", action="connection", status="success", metadata={})
    store(event_repo, [event_no_port])
    result = evaluator.evaluate(rules["NET-001"], event_no_port)
    assert not result.matched and "destination_port" in result.reason


def test_missing_optional_fields_do_not_crash_any_rule(evaluator, rules):
    bare = make(username=None, source_ip=None, metadata={})
    for rule in rules.values():
        assert evaluator.evaluate(rule, bare).matched is False


@pytest.mark.parametrize("conditions", [
    {"event_type": "authentication", "stages": [{"status": "failed"}]},       # the Step 3 seed shape
    {"event_type": "authentication", "threshold": 5},                         # no window
    {"event_type": "authentication", "threshold": 0, "window_minutes": 5},
    {"event_type": "authentication", "threshold": 5, "window_minutes": 100000},
    {"event_type": "authentication", "threshold": 5, "window_minutes": 5, "correlation_field": "password"},
    {"event_type": "authentication", "window_minutes": 5},                    # window without threshold
    {"threshold": 5, "window_minutes": 5},                                    # matches everything
    {"event_type": "bogus"},
    {"event_type": "authentication", "metadata": {"$where": "sleep(1000)"}},
    {"event_type": "authentication", "metadata": {"a.b": 1}},
    {"event_type": "authentication", "metadata": {"reason": {"$ne": None}}},  # operators are not values
    {"event_type": "network", "threshold": 3, "window_minutes": 5, "distinct_field": "metadata.a.b"},
    {"event_type": "network", "distinct_field": "metadata.destination_port"}, # distinct without threshold
    {"event_type": "authentication", "correlation_field": "source_ip"},       # stateless with correlation
    {"event_type": "authentication", "status": "success", "window_minutes": 5, "threshold": 2,
     "preceded_by": {"status": "failed", "min_count": 1}},
    {"event_type": "authentication", "window_minutes": 5, "preceded_by": {"min_count": 1}},  # empty stage
    {"__import__('os').system('x')": 1},
])
def test_invalid_conditions_are_rejected_safely(evaluator, rules, conditions):
    rule = rules["AUTH-002"].model_copy(update={"conditions": conditions})
    with pytest.raises(InvalidRuleError):
        evaluator.evaluate(rule, make())


def test_invalid_rule_error_does_not_echo_stored_values(evaluator, rules):
    secret = "SECRET-VALUE-123"
    rule = rules["AUTH-002"].model_copy(update={"conditions": {"event_type": secret}})
    with pytest.raises(InvalidRuleError) as info:
        evaluator.evaluate(rule, make())
    assert secret not in str(info.value)
