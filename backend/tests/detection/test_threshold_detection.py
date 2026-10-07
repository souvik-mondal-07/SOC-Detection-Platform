"""AUTH-001 threshold and time-window behaviour."""

from tests.detection.conftest import make, store


def failures(count, spacing=10, **kw):
    return [make(i * spacing, **kw) for i in range(count)]


def test_four_failures_no_match(evaluator, event_repo, rules):
    events = store(event_repo, failures(4))
    result = evaluator.evaluate(rules["AUTH-001"], events[-1])
    assert not result.matched and result.severity is None
    assert result.details["observed"] == 4 and result.details["threshold"] == 5


def test_five_failures_match(evaluator, event_repo, rules):
    events = store(event_repo, failures(5))
    result = evaluator.evaluate(rules["AUTH-001"], events[-1])
    assert result.matched and result.rule_id == "AUTH-001" and result.severity == "high"
    assert result.reason == "5 failed authentication events from the same source IP within 5 minutes"
    assert result.matched_event_ids == [e.event_id for e in events]
    assert result.details["correlation_value"] == "192.168.1.20"


def test_six_failures_match(evaluator, event_repo, rules):
    events = store(event_repo, failures(6))
    result = evaluator.evaluate(rules["AUTH-001"], events[-1])
    assert result.matched and result.details["observed"] == 6


def test_every_event_of_a_burst_is_reported_including_the_first(evaluator, event_repo, rules):
    events = store(event_repo, failures(5))
    assert all(evaluator.evaluate(rules["AUTH-001"], e).matched for e in events)


def test_failures_spread_over_more_than_the_window_do_not_match(evaluator, event_repo, rules):
    events = store(event_repo, failures(5, spacing=90))  # 4 gaps x 90 s = 360 s > 300 s
    assert not any(evaluator.evaluate(rules["AUTH-001"], e).matched for e in events)


def test_window_boundary_is_inclusive(evaluator, event_repo, rules):
    events = store(event_repo, [make(0), make(75), make(150), make(225), make(300)])  # exactly 5 minutes
    assert evaluator.evaluate(rules["AUTH-001"], events[-1]).matched
    events2 = store(event_repo, [make(0, source_ip="10.1.1.1"), make(75, source_ip="10.1.1.1"), make(150, source_ip="10.1.1.1"),
                                 make(225, source_ip="10.1.1.1"), make(301, source_ip="10.1.1.1")])  # one second too long
    assert not evaluator.evaluate(rules["AUTH-001"], events2[-1]).matched


def test_old_failures_outside_window_are_ignored_but_recent_burst_still_matches(evaluator, event_repo, rules):
    old = failures(3, spacing=10)  # at 0..20 s
    burst = [make(3600 + i, ) for i in range(5)]  # an hour later
    store(event_repo, old + burst)
    assert evaluator.evaluate(rules["AUTH-001"], burst[-1]).matched
    # 2 recent failures + 3 old ones are not combined
    mixed = [make(7200 + i * 5, source_ip="10.2.2.2") for i in range(2)]
    store(event_repo, [make(i * 5, source_ip="10.2.2.2") for i in range(3)] + mixed)
    assert not evaluator.evaluate(rules["AUTH-001"], mixed[-1]).matched


def test_successes_and_other_event_types_do_not_count(evaluator, event_repo, rules):
    other_type = make(47, event_type="web", source="web_application", action="http_request")
    events = store(event_repo, failures(4) + [make(45, status="success"), other_type])
    assert not evaluator.evaluate(rules["AUTH-001"], events[3]).matched


def test_rule_without_correlation_field_defaults_to_source_ip(evaluator, event_repo, rules):
    """The Step 3 AUTH-001 document has no correlation_field."""
    legacy = rules["AUTH-001"].model_copy(update={"conditions": {
        "event_type": "authentication", "status": "failed", "threshold": 5, "window_minutes": 5}})
    events = store(event_repo, failures(3, source_ip="10.3.3.3") + failures(3, source_ip="10.4.4.4"))
    assert not evaluator.evaluate(legacy, events[2]).matched  # 3 + 3 are not combined
    more = store(event_repo, failures(5, source_ip="10.5.5.5"))
    assert evaluator.evaluate(legacy, more[0]).matched


def test_threshold_can_correlate_by_username(evaluator, event_repo, rules):
    by_user = rules["AUTH-001"].model_copy(update={"conditions": {
        "event_type": "authentication", "status": "failed", "threshold": 5, "window_minutes": 5,
        "correlation_field": "username"}})
    events = store(event_repo, [make(i, source_ip=f"10.9.9.{i}", username="victim") for i in range(5)])
    result = evaluator.evaluate(by_user, events[0])
    assert result.matched and "same username" in result.reason
    assert not evaluator.evaluate(rules["AUTH-001"], events[0]).matched  # by source IP each IP has one
