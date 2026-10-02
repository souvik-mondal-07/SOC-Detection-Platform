from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.database import COLLECTION_ALERTS
from app.models.alert import Alert
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    model = Alert
    collection_name = COLLECTION_ALERTS
    id_field = "alert_id"
    indexes = (
        IndexModel([("alert_id", ASCENDING)], name="uq_alert_id", unique=True),
        IndexModel([("created_at", DESCENDING)], name="ix_created_at"),  # newest alerts first
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="ix_status_created_at"),  # triage queue
        IndexModel([("severity", ASCENDING), ("created_at", DESCENDING)], name="ix_severity_created_at"),  # filter by severity
        IndexModel([("rule_id", ASCENDING), ("created_at", DESCENDING)], name="ix_rule_id_created_at"),  # alerts per rule, tuning
        IndexModel([("source_ip", ASCENDING), ("created_at", DESCENDING)], name="ix_source_ip_created_at"),  # alerts for one IP
    )
