"""Detection service: load events and enabled rules, run the engine, return results.

No HTTP code here. It only reads events and rules; it never creates alerts or
writes anything. Database access goes through the repositories.
"""

from collections.abc import Sequence

from app.detection.engine import DetectionEngine
from app.detection.result import BatchDetection, EventDetection
from app.detection.rule_evaluator import RuleEvaluator
from app.models.event import SecurityEvent
from app.models.rule import DetectionRule
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.services.ingestion_service import EventNotFoundError


class DetectionService:
    def __init__(self, event_repository: EventRepository, rule_repository: DetectionRuleRepository) -> None:
        self._events = event_repository
        self._rules = rule_repository
        self._engine = DetectionEngine(RuleEvaluator(event_repository))

    def evaluate_event_id(self, event_id: str) -> EventDetection:
        """Raises EventNotFoundError if the event does not exist."""
        event = self._events.get_event_by_id(event_id)
        if event is None:
            raise EventNotFoundError(event_id)
        return self.evaluate_event(event)

    def evaluate_event(self, event: SecurityEvent, rules: Sequence[DetectionRule] | None = None) -> EventDetection:
        enabled_rules = self._rules.get_enabled_rules() if rules is None else rules
        return self._engine.evaluate_event(event, enabled_rules)

    def evaluate_event_ids(self, event_ids: Sequence[str]) -> BatchDetection:
        """Evaluate several events with one rule load. Unknown IDs are reported, not fatal."""
        unique_ids = list(dict.fromkeys(event_ids))
        found = {event.event_id: event for event in self._events.get_events_by_ids(unique_ids)}
        rules = self._rules.get_enabled_rules()
        return BatchDetection(
            detections=[self._engine.evaluate_event(found[i], rules) for i in unique_ids if i in found],
            not_found_event_ids=[i for i in unique_ids if i not in found],
        )
