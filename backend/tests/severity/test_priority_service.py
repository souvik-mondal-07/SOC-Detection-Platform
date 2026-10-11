from datetime import datetime, timedelta, timezone

import pytest

from app.core.severity import SEVERITY_BASE_SCORE, SEVERITY_ORDER
from app.services.priority_service import MAX_CONTEXT_BOOST, PriorityService

NOW = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
svc = PriorityService()


def score(severity, **kw):
    return svc.calculate(severity, now=NOW, **kw)


@pytest.mark.parametrize("severity,expected", [("low", 25), ("medium", 50), ("high", 75), ("critical", 100)])
def test_single_old_event_gets_base_score(severity, expected):
    result = score(severity, event_count=1, last_event_at=NOW - timedelta(days=1))
    assert result.score == expected and result.reason == f"{severity.capitalize()} severity rule"


def test_event_count_increases_score_in_steps():
    scores = [score("high", event_count=n).score for n in (1, 2, 5, 20, 500)]
    assert scores == [75, 77, 80, 83, 83]


def test_correlation_requires_multiple_events():
    assert score("high", event_count=1, correlated=True).score == 75
    assert score("high", event_count=5, correlated=True).score == 83


def test_recency_boost():
    assert score("medium", last_event_at=NOW - timedelta(minutes=5)).score == 53
    assert score("medium", last_event_at=NOW - timedelta(minutes=30)).score == 51
    assert score("medium", last_event_at=NOW - timedelta(hours=3)).score == 50
    assert score("medium", last_event_at=None).score == 50
    assert score("medium", last_event_at=NOW + timedelta(hours=1)).score == 53  # clock skew = just now
    assert score("medium", last_event_at=(NOW - timedelta(minutes=5)).replace(tzinfo=None)).score == 53  # naive = UTC


def test_reason_is_concise_and_hides_internals():
    result = score("high", event_count=5, correlated=True, last_event_at=NOW)
    assert result.reason == "High severity rule with multiple correlated events and recent activity"
    assert score("medium", event_count=3).reason == "Medium severity rule with multiple events"
    assert score("low", last_event_at=NOW).reason == "Low severity rule with recent activity"


def test_deterministic():
    kw = dict(event_count=7, correlated=True, last_event_at=NOW - timedelta(minutes=10))
    assert len({(r.score, r.reason) for r in (score("high", **kw) for _ in range(50))}) == 1


def test_never_leaves_0_to_100():
    for severity in SEVERITY_ORDER:
        for count in (0, -5, 1, 2, 5, 20, 10_000):
            for correlated in (True, False):
                s = score(severity, event_count=count, correlated=correlated, last_event_at=NOW).score
                assert 0 <= s <= 100
    assert score("critical", event_count=10_000, correlated=True, last_event_at=NOW).score == 100


def test_context_can_never_outrank_a_higher_severity():
    """Max boost is below the gap between bases, so severity stays the primary factor."""
    for lower, higher in zip(SEVERITY_ORDER, SEVERITY_ORDER[1:]):
        best_lower = score(lower, event_count=10_000, correlated=True, last_event_at=NOW).score
        worst_higher = score(higher, event_count=1).score
        assert best_lower < worst_higher
        assert SEVERITY_BASE_SCORE[lower] + MAX_CONTEXT_BOOST == best_lower or lower.value == "critical"


def test_low_never_becomes_critical():
    assert score("low", event_count=10_000, correlated=True, last_event_at=NOW).score < 50


def test_unknown_severity_rejected():
    with pytest.raises(ValueError):
        score("urgent")
