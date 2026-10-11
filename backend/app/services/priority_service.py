"""Deterministic, explainable alert priority scoring (0-100).

    score = base(severity) + event-count boost + correlation boost + recency boost, clamped to 0-100

Rule severity is the primary factor. The boosts are small and capped (at most +14 in
total), which is smaller than the 25-point gap between severity bases, so an alert can
never be ranked above a higher-severity alert because of context alone, and a LOW rule
can never turn into a CRITICAL score.

This service is pure: no database access, no HTTP, no detection, no alert creation.
The same inputs always give the same result.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.severity import base_score, clamp_score, to_severity
from app.models.common import Severity

# (minimum contributing events, boost) - first match wins, highest threshold first.
EVENT_COUNT_BOOSTS: tuple[tuple[int, int], ...] = ((20, 8), (5, 5), (2, 2))
CORRELATION_BOOST = 3
# (maximum age in minutes, boost) - first match wins, smallest window first.
RECENCY_BOOSTS: tuple[tuple[int, int], ...] = ((15, 3), (60, 1))

MAX_CONTEXT_BOOST = max(b for _, b in EVENT_COUNT_BOOSTS) + CORRELATION_BOOST + max(b for _, b in RECENCY_BOOSTS)


@dataclass(frozen=True)
class PriorityResult:
    score: int
    reason: str


class PriorityService:
    def calculate(
        self,
        severity: "Severity | str",
        *,
        event_count: int = 1,
        correlated: bool = False,
        last_event_at: datetime | None = None,
        now: datetime | None = None,
    ) -> PriorityResult:
        """Score one alert.

        event_count   number of contributing events
        correlated    the detection grouped several events by a shared value (e.g. source IP)
        last_event_at time of the newest contributing event; None means no recency boost
        now           injectable clock for deterministic tests (defaults to current UTC time)
        """
        level = to_severity(severity)
        score = base_score(level)

        count_boost = next((boost for minimum, boost in EVENT_COUNT_BOOSTS if event_count >= minimum), 0)
        correlation_boost = CORRELATION_BOOST if correlated and event_count >= 2 else 0
        recency_boost = self._recency_boost(last_event_at, now)

        score = clamp_score(score + count_boost + correlation_boost + recency_boost)
        return PriorityResult(score=score, reason=_reason(level, event_count, correlation_boost > 0, recency_boost > 0))

    @staticmethod
    def _recency_boost(last_event_at: datetime | None, now: datetime | None) -> int:
        if last_event_at is None:
            return 0
        if last_event_at.tzinfo is None:
            last_event_at = last_event_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        age = max(current - last_event_at, timedelta(0))  # future timestamps count as "just now"
        return next((boost for minutes, boost in RECENCY_BOOSTS if age <= timedelta(minutes=minutes)), 0)


def _reason(severity: Severity, event_count: int, correlated: bool, recent: bool) -> str:
    factors = []
    if correlated:
        factors.append("multiple correlated events")
    elif event_count >= 2:
        factors.append("multiple events")
    if recent:
        factors.append("recent activity")
    text = f"{severity.value.capitalize()} severity rule"
    return f"{text} with {' and '.join(factors)}" if factors else text
