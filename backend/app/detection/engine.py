"""Coordinates rule evaluation for an event. Stateless: rules are passed in, storage is behind the evaluator."""

import logging
from collections.abc import Sequence

from app.detection.base import InvalidRuleError
from app.detection.result import EventDetection
from app.detection.rule_evaluator import RuleEvaluator
from app.models.event import SecurityEvent
from app.models.rule import DetectionRule

logger = logging.getLogger("soc.detection")


class DetectionEngine:
    def __init__(self, evaluator: RuleEvaluator) -> None:
        self._evaluator = evaluator

    def evaluate_event(self, event: SecurityEvent, rules: Sequence[DetectionRule]) -> EventDetection:
        """Evaluate every enabled rule. Disabled rules are never evaluated and can never match.
        A rule with invalid conditions is logged and skipped; it does not stop the others.

        Returns detection results only. Nothing is stored and no alert is created."""
        detection = EventDetection(event_id=event.event_id)
        for rule in rules:
            if not rule.enabled:
                continue
            try:
                detection.results.append(self._evaluator.evaluate(rule, event))
            except InvalidRuleError as exc:
                logger.warning("Skipping rule %s: %s", rule.rule_id, exc)
                detection.skipped_rule_ids.append(rule.rule_id)
                continue
            detection.rules_evaluated += 1
        return detection

    def evaluate_events(self, events: Sequence[SecurityEvent], rules: Sequence[DetectionRule]) -> list[EventDetection]:
        return [self.evaluate_event(event, rules) for event in events]
