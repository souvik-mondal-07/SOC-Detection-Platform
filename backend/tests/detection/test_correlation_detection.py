"""Correlation: events are grouped by source IP (or username), never counted globally."""

from tests.detection.conftest import make, net, store, web


def test_different_source_ips_are_not_combined(evaluator, event_repo, rules):
    a = [make(i * 5, source_ip="192.168.1.20") for i in range(3)]
    b = [make(i * 5 + 1, source_ip="192.168.1.50") for i in range(3)]
    store(event_repo, a + b)  # 6 failures in total, but only 3 per IP
    assert not evaluator.evaluate(rules["AUTH-001"], a[-1]).matched
    assert not evaluator.evaluate(rules["AUTH-001"], b[-1]).matched


def test_only_the_offending_ip_matches(evaluator, event_repo, rules):
    noisy = [make(i * 5, source_ip="192.168.1.20") for i in range(5)]
    quiet = [make(i * 5 + 1, source_ip="192.168.1.50") for i in range(2)]
    store(event_repo, noisy + quiet)
    assert evaluator.evaluate(rules["AUTH-001"], noisy[0]).matched
    assert not evaluator.evaluate(rules["AUTH-001"], quiet[0]).matched


def test_the_spec_scenario_5_vs_2(evaluator, event_repo, rules):
    store(event_repo, [make(i, source_ip="192.168.1.20") for i in range(5)])
    two = store(event_repo, [make(i, source_ip="192.168.1.50") for i in range(2)])
    assert not evaluator.evaluate(rules["AUTH-001"], two[1]).matched


def test_web_errors_are_grouped_per_ip(evaluator, event_repo, rules):
    store(event_repo, [web(i, source_ip="10.0.0.1") for i in range(6)])
    other = store(event_repo, [web(i + 0.5, source_ip="10.0.0.2") for i in range(6)])
    assert not evaluator.evaluate(rules["WEB-001"], other[-1]).matched  # 6 + 6 are not 12


def test_unique_ports_are_grouped_per_ip(evaluator, event_repo, rules):
    store(event_repo, [net(i, 1000 + i, source_ip="10.0.0.1") for i in range(6)])
    other = store(event_repo, [net(i, 2000 + i, source_ip="10.0.0.2") for i in range(6)])
    assert not evaluator.evaluate(rules["NET-001"], other[-1]).matched  # 12 ports overall, 6 per IP


def test_sequence_requires_same_source_ip(evaluator, event_repo, rules):
    store(event_repo, [make(i, source_ip="10.0.0.1") for i in range(3)])
    success = store(event_repo, [make(100, status="success", source_ip="10.0.0.2")])[0]
    assert not evaluator.evaluate(rules["AUTH-003"], success).matched


def test_correlation_ignores_events_with_no_ip(evaluator, event_repo, rules):
    store(event_repo, [make(i, source_ip=None) for i in range(5)])
    target = store(event_repo, [make(6, source_ip="10.0.0.3")])[0]
    assert not evaluator.evaluate(rules["AUTH-001"], target).matched
