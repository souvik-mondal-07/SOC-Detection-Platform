import pytest

from app.core.severity import (
    MAX_PRIORITY_SCORE, MIN_PRIORITY_SCORE, SEVERITY_BASE_SCORE, SEVERITY_ORDER, base_score, clamp_score, to_severity,
)
from app.models.common import Severity


def test_exactly_four_levels_in_order():
    assert [s.value for s in Severity] == ["low", "medium", "high", "critical"]  # canonical stored form is lowercase
    assert SEVERITY_ORDER == (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)


@pytest.mark.parametrize("severity,score", [("low", 25), ("medium", 50), ("high", 75), ("critical", 100)])
def test_base_scores(severity, score):
    assert base_score(severity) == score == SEVERITY_BASE_SCORE[Severity(severity)]


def test_base_scores_strictly_increase():
    scores = [SEVERITY_BASE_SCORE[s] for s in SEVERITY_ORDER]
    assert scores == sorted(scores) and len(set(scores)) == 4


def test_to_severity_accepts_enum_and_any_case():
    assert to_severity(Severity.HIGH) is Severity.HIGH
    assert to_severity("HIGH") is Severity.HIGH and to_severity(" low ") is Severity.LOW


@pytest.mark.parametrize("bad", ["urgent", "", None, 5])
def test_to_severity_rejects_unknown(bad):
    with pytest.raises(ValueError):
        to_severity(bad)


@pytest.mark.parametrize("value,expected", [(-10, 0), (0, 0), (57, 57), (100, 100), (125, 100), (500, 100)])
def test_clamp(value, expected):
    assert clamp_score(value) == expected
    assert MIN_PRIORITY_SCORE <= clamp_score(value) <= MAX_PRIORITY_SCORE
