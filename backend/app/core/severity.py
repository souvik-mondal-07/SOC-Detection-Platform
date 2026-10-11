"""Single source of truth for severity levels, their definitions and base priority scores.

The `Severity` enum itself lives in `app.models.common` (Steps 3-8 already store and
return it). Its canonical stored/API representation is lowercase:
`low`, `medium`, `high`, `critical`. This module adds the scores and wording on top of
that enum instead of defining a second one.

Rule severity is authoritative: an alert's severity always comes from its detection
rule, never from an event or a client.
"""

from app.models.common import Severity

MIN_PRIORITY_SCORE = 0
MAX_PRIORITY_SCORE = 100

# Base priority score per severity. Do not duplicate these numbers elsewhere.
SEVERITY_BASE_SCORE: dict[Severity, int] = {
    Severity.LOW: 25,
    Severity.MEDIUM: 50,
    Severity.HIGH: 75,
    Severity.CRITICAL: 100,
}

SEVERITY_MEANING: dict[Severity, str] = {
    Severity.LOW: "Minor anomaly",
    Severity.MEDIUM: "Suspicious activity",
    Severity.HIGH: "Strong suspicious activity",
    Severity.CRITICAL: "Potentially severe impact",
}

# Lowest to highest.
SEVERITY_ORDER: tuple[Severity, ...] = (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)


def to_severity(value: "Severity | str") -> Severity:
    """Accept the enum or its stored string ("high" / "HIGH"); raise ValueError otherwise."""
    if isinstance(value, Severity):
        return value
    try:
        return Severity(str(value).strip().lower())
    except ValueError:
        raise ValueError(f"unknown severity: {value!r}") from None


def base_score(severity: "Severity | str") -> int:
    return SEVERITY_BASE_SCORE[to_severity(severity)]


def clamp_score(score: int) -> int:
    return max(MIN_PRIORITY_SCORE, min(MAX_PRIORITY_SCORE, int(score)))
