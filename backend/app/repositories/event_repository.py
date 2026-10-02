from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.database import COLLECTION_EVENTS
from app.models.event import SecurityEvent
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[SecurityEvent]):
    model = SecurityEvent
    collection_name = COLLECTION_EVENTS
    id_field = "event_id"
    # Compound indexes start with the filter field, so they also serve
    # lookups on that field alone (no separate single-field index needed).
    indexes = (
        IndexModel([("event_id", ASCENDING)], name="uq_event_id", unique=True),  # no duplicate events
        IndexModel([("timestamp", DESCENDING)], name="ix_timestamp"),  # newest-first, time-range queries
        IndexModel([("source_ip", ASCENDING), ("timestamp", DESCENDING)], name="ix_source_ip_timestamp"),  # events from one IP over time
        IndexModel([("event_type", ASCENDING), ("timestamp", DESCENDING)], name="ix_event_type_timestamp"),  # per-type windows for rules
        IndexModel([("username", ASCENDING), ("timestamp", DESCENDING)], name="ix_username_timestamp"),  # activity of one account
    )
