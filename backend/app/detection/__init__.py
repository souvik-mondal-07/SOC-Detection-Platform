"""Rule-based detection engine (Step 6).

Evaluates normalised security events against data-driven rules and returns
DetectionResult objects. It never creates alerts and never runs rule content
as code.
"""

from app.detection.engine import DetectionEngine
from app.detection.result import BatchDetection, DetectionResult, EventDetection
from app.detection.rule_evaluator import RuleEvaluator

__all__ = ["BatchDetection", "DetectionEngine", "DetectionResult", "EventDetection", "RuleEvaluator"]
