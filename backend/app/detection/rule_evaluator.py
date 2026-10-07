"""Evaluates one rule against one event (or several events, one at a time).

Rule kinds
  stateless  the event alone satisfies the filters
  threshold  >= N matching events (or N distinct values) from the same correlation
             value inside a window of `window_minutes` that contains the event
  sequence   the event matches, and >= min_count `preceded_by` events from the same
             correlation value occurred in the `window_minutes` before it

A threshold window "contains the event" rather than ending at it, so every event
of a burst is reported as part of that burst, including the first one. Events that
are later than the evaluated event can therefore complete a window.
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.detection.base import EventStore
from app.detection.conditions import RuleConditions, RuleKind, field_value, parse_conditions
from app.detection.result import DetectionResult
from app.models.event import SecurityEvent
from app.models.rule import DetectionRule

MAX_EVENTS_PER_EVALUATION = 5000  # events loaded for one rule evaluation (bounded read)
MAX_REPORTED_EVENT_IDS = 100


class RuleEvaluator:
    def __init__(self, event_store: EventStore) -> None:
        self._store = event_store

    def evaluate(self, rule: DetectionRule, event: SecurityEvent) -> DetectionResult:
        """Evaluate `rule` for `event`. Raises InvalidRuleError if the stored conditions are unusable."""
        if not rule.enabled:
            return self._no_match(rule, event, "Rule is disabled")
        conditions = parse_conditions(rule.conditions)

        if not conditions.matches(event):
            return self._no_match(rule, event, "Event did not satisfy rule conditions")

        if conditions.kind is RuleKind.STATELESS:
            return self._match(rule, event, f"Event matched rule conditions: {conditions.describe('event')}", [event.event_id], {})

        correlation_field = conditions.correlation_field
        correlation_value = field_value(event, correlation_field)
        if correlation_value is None:
            return self._no_match(rule, event, f"Event has no {conditions.correlation_label}, so it cannot be correlated")

        if conditions.kind is RuleKind.SEQUENCE:
            return self._evaluate_sequence(rule, event, conditions, correlation_value)
        return self._evaluate_threshold(rule, event, conditions, correlation_value)

    def evaluate_events(self, rule: DetectionRule, events: list[SecurityEvent]) -> list[DetectionResult]:
        return [self.evaluate(rule, event) for event in events]

    # -- threshold / distinct --------------------------------------------------------

    def _evaluate_threshold(self, rule, event, c: RuleConditions, correlation_value) -> DetectionResult:
        window = timedelta(minutes=c.window_minutes)
        distinct = c.kind is RuleKind.DISTINCT
        if distinct and field_value(event, c.distinct_field) is None:
            return self._no_match(rule, event, f"Event has no {c.distinct_field}, so it cannot be counted")

        query = {**c.query_filters(), c.correlation_field: correlation_value}
        search = {"start": event.timestamp - window, "end": event.timestamp + window}

        # Cheap indexed count first: skip loading anything when the threshold is out of reach.
        nearby = self._store.count_matching_events(**query, **search)
        if nearby < c.threshold:
            return self._no_match(
                rule, event,
                f"Threshold not reached: {nearby} matching event(s) within {c.window_minutes} minutes of this event, {c.threshold} required",
                {"threshold": c.threshold, "window_minutes": c.window_minutes, "observed": nearby},
            )

        candidates = self._with_event(self._store.find_matching_events(**query, **search, limit=MAX_EVENTS_PER_EVALUATION), event)
        if distinct:
            candidates = [e for e in candidates if field_value(e, c.distinct_field) is not None]
            key_of = lambda e: field_value(e, c.distinct_field)  # noqa: E731
        else:
            key_of = lambda e: e.event_id  # noqa: E731
        observed, burst = _best_window(candidates, event.timestamp, window, key_of)

        details: dict[str, Any] = {
            "threshold": c.threshold,
            "window_minutes": c.window_minutes,
            "correlation_field": c.correlation_field,
            "correlation_value": correlation_value,
            "observed": observed,
        }
        if observed < c.threshold:
            return self._no_match(
                rule, event,
                f"Threshold not reached: {observed} {'distinct values' if distinct else 'matching event(s)'} within {c.window_minutes} minutes, {c.threshold} required",
                details,
            )

        if burst:
            details["window_start"], details["window_end"] = burst[0].timestamp.isoformat(), burst[-1].timestamp.isoformat()
        if distinct:
            reason = (f"{observed} distinct {c.distinct_field} values across {c.describe()} "
                      f"from the same {c.correlation_label} within {c.window_minutes} minutes")
        else:
            reason = f"{observed} {c.describe()} from the same {c.correlation_label} within {c.window_minutes} minutes"
        return self._match(rule, event, reason, [e.event_id for e in burst], details)

    # -- sequence ---------------------------------------------------------------------

    def _evaluate_sequence(self, rule, event, c: RuleConditions, correlation_value) -> DetectionResult:
        earlier = c.preceded_by
        window = timedelta(minutes=c.window_minutes)
        query = {**earlier.query_filters(), c.correlation_field: correlation_value}
        search = {"start": event.timestamp - window, "end": event.timestamp}
        details: dict[str, Any] = {
            "required_prior_events": earlier.min_count,
            "window_minutes": c.window_minutes,
            "correlation_field": c.correlation_field,
            "correlation_value": correlation_value,
        }

        nearby = self._store.count_matching_events(**query, **search)
        if nearby < earlier.min_count:
            return self._no_match(
                rule, event,
                f"Sequence not satisfied: {nearby} preceding event(s) within {c.window_minutes} minutes, {earlier.min_count} required",
                {**details, "observed": nearby},
            )

        found = self._store.find_matching_events(**query, **search, limit=MAX_EVENTS_PER_EVALUATION)
        prior = [e for e in found if e.event_id != event.event_id and earlier.matches(e)]
        details["observed"] = len(prior)
        if len(prior) < earlier.min_count:
            return self._no_match(
                rule, event,
                f"Sequence not satisfied: {len(prior)} preceding event(s) within {c.window_minutes} minutes, {earlier.min_count} required",
                details,
            )

        reason = (f"{c.describe('event')} preceded by {len(prior)} {earlier.describe()} "
                  f"from the same {c.correlation_label} within {c.window_minutes} minutes")
        ids = [e.event_id for e in prior][-(MAX_REPORTED_EVENT_IDS - 1):] + [event.event_id]
        return self._match(rule, event, reason, ids, details)

    # -- helpers ----------------------------------------------------------------------

    @staticmethod
    def _with_event(found: list[SecurityEvent], event: SecurityEvent) -> list[SecurityEvent]:
        """Make sure the evaluated event is part of the list (it may be missing from a truncated read)."""
        if any(item.event_id == event.event_id for item in found):
            return found
        return sorted([*found, event], key=lambda e: (e.timestamp, e.event_id))

    @staticmethod
    def _no_match(rule: DetectionRule, event: SecurityEvent, reason: str, details: dict[str, Any] | None = None) -> DetectionResult:
        return DetectionResult(matched=False, rule_id=rule.rule_id, rule_name=rule.name, category=rule.category,
                               event_id=event.event_id, reason=reason, details=details or {})

    @staticmethod
    def _match(rule: DetectionRule, event: SecurityEvent, reason: str, event_ids: list[str], details: dict[str, Any]) -> DetectionResult:
        return DetectionResult(matched=True, rule_id=rule.rule_id, rule_name=rule.name, category=rule.category,
                               event_id=event.event_id, reason=reason, severity=rule.severity,
                               matched_event_ids=event_ids[:MAX_REPORTED_EVENT_IDS], details=details)


def _best_window(events: list[SecurityEvent], anchor: datetime, window: timedelta, key_of) -> tuple[int, list[SecurityEvent]]:
    """Largest number of distinct keys inside any window of length `window` that contains `anchor`.

    `events` must be sorted by timestamp. Candidate windows start at an event no earlier
    than anchor - window and no later than anchor, so each one includes the anchor.
    Returns (distinct key count, events in that window).
    """
    best_count, best_range = 0, (0, 0)
    counts: Counter = Counter()
    right = 0
    for left, current in enumerate(events):
        limit = current.timestamp + window
        while right < len(events) and events[right].timestamp <= limit:
            counts[key_of(events[right])] += 1
            right += 1
        if anchor - window <= current.timestamp <= anchor and len(counts) > best_count:
            best_count, best_range = len(counts), (left, right)
        key = key_of(current)
        counts[key] -= 1
        if counts[key] == 0:
            del counts[key]
    return best_count, events[best_range[0]:best_range[1]]
