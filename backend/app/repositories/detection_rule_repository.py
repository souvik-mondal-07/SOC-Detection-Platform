from pymongo import ASCENDING, IndexModel

from app.core.database import COLLECTION_RULES
from app.models.rule import DetectionRule
from app.repositories.base import BaseRepository


class DetectionRuleRepository(BaseRepository[DetectionRule]):
    model = DetectionRule
    collection_name = COLLECTION_RULES
    id_field = "rule_id"
    indexes = (
        IndexModel([("rule_id", ASCENDING)], name="uq_rule_id", unique=True),
        IndexModel([("category", ASCENDING)], name="ix_category"),  # list rules by category
        IndexModel([("enabled", ASCENDING)], name="ix_enabled"),  # engine loads enabled rules
    )
