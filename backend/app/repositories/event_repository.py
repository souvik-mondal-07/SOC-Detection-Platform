import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import Any

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import BulkWriteError

from app.core.database import COLLECTION_EVENTS
from app.core.errors import DuplicateRecordError
from app.models.event import SecurityEvent
from app.repositories.base import BaseRepository, translate_db_errors

_DUPLICATE_KEY_CODE = 11000

# Stateful detection reads a bounded slice of events per evaluation, never the whole collection.
MAX_MATCH_LIMIT = 5000
_METADATA_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_SCALAR_TYPES = (str, int, bool)


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


class EventRepository(BaseRepository[SecurityEvent]):
    model = SecurityEvent
    collection_name = COLLECTION_EVENTS
    id_field = "event_id"
    # Compound indexes start with the filter field, so they also serve
    # lookups on that field alone (no separate single-field index needed).
    # Every GET /events filter is paired with timestamp because results are newest-first.
    indexes = (
        IndexModel([("event_id", ASCENDING)], name="uq_event_id", unique=True),  # no duplicate events
        IndexModel([("timestamp", DESCENDING)], name="ix_timestamp"),  # newest-first, unfiltered listing
        IndexModel([("source_ip", ASCENDING), ("timestamp", DESCENDING)], name="ix_source_ip_timestamp"),  # events from one IP over time
        IndexModel([("event_type", ASCENDING), ("timestamp", DESCENDING)], name="ix_event_type_timestamp"),  # per-type windows for rules
        IndexModel([("username", ASCENDING), ("timestamp", DESCENDING)], name="ix_username_timestamp"),  # activity of one account
        IndexModel([("source", ASCENDING), ("timestamp", DESCENDING)], name="ix_source_timestamp"),  # filter by source (Step 4)
        IndexModel([("status", ASCENDING), ("timestamp", DESCENDING)], name="ix_status_timestamp"),  # filter by status (Step 4)
        # Step 6 stateful detection: equality fields first, timestamp last for the window range.
        IndexModel(
            [("event_type", ASCENDING), ("status", ASCENDING), ("source_ip", ASCENDING), ("timestamp", ASCENDING)],
            name="ix_detection_type_status_ip_timestamp",  # N events of one type/status from one IP in a window
        ),
        IndexModel(
            [("event_type", ASCENDING), ("status", ASCENDING), ("username", ASCENDING), ("timestamp", ASCENDING)],
            name="ix_detection_type_status_user_timestamp",  # same, correlated by username
        ),
    )

    def create_event(self, event: SecurityEvent) -> SecurityEvent:
        return self.create(event)

    def create_many(self, events: Sequence[SecurityEvent]) -> int:
        """Insert many events in one call. Returns how many were stored."""
        if not events:
            return 0
        documents = [event.to_document() for event in events]
        try:
            with translate_db_errors():
                result = self._collection.insert_many(documents, ordered=False)
        except BulkWriteError as exc:
            write_errors = exc.details.get("writeErrors", [])
            if write_errors and all(e.get("code") == _DUPLICATE_KEY_CODE for e in write_errors):
                raise DuplicateRecordError("duplicate event_id in batch") from exc
            raise
        return len(result.inserted_ids)

    def get_event_by_id(self, event_id: str) -> SecurityEvent | None:
        return self.find_by_id(event_id)

    def get_events(
        self,
        *,
        source: Any = None,
        event_type: Any = None,
        status: Any = None,
        source_ip: str | None = None,
        limit: int = 50,
    ) -> list[SecurityEvent]:
        """Newest events first. Only these four filters exist; the query is built here
        from fixed field names, so callers can never inject query operators."""
        filters = {"source": source, "event_type": event_type, "status": status, "source_ip": source_ip}
        query = {name: _plain(value) for name, value in filters.items() if value is not None}
        return self.find_many(query, sort=[("timestamp", DESCENDING)], limit=limit)

    def get_events_by_ids(self, event_ids: Sequence[str]) -> list[SecurityEvent]:
        """Fetch several events with one query. Order is not guaranteed; unknown IDs are simply absent."""
        if not event_ids:
            return []
        with translate_db_errors():
            documents = list(self._collection.find({"event_id": {"$in": list(event_ids)}}, {"_id": 0}))
        return [SecurityEvent.from_document(document) for document in documents]

    # -- queries used by the detection engine (Step 6) --------------------------------

    def count_matching_events(self, **criteria: Any) -> int:
        """Count events matching the criteria (see build_match_query). Does not load them."""
        query = build_match_query(**criteria)
        with translate_db_errors():
            return self._collection.count_documents(query)

    def find_matching_events(self, *, limit: int = MAX_MATCH_LIMIT, **criteria: Any) -> list[SecurityEvent]:
        """Matching events, oldest first, at most `limit` (never the whole collection)."""
        if not 1 <= limit <= MAX_MATCH_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_MATCH_LIMIT}")
        query = build_match_query(**criteria)
        with translate_db_errors():
            cursor = self._collection.find(query, {"_id": 0}).sort([("timestamp", ASCENDING), ("event_id", ASCENDING)]).limit(limit)
            documents = list(cursor)
        return [SecurityEvent.from_document(document) for document in documents]


def build_match_query(
    *,
    event_type: Any = None,
    status: Any = None,
    action: str | None = None,
    source: str | None = None,
    username: str | None = None,
    source_ip: str | None = None,
    username_present: bool = False,
    source_ip_present: bool = False,
    metadata: Mapping[str, Any] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    """Build a MongoDB query from fixed field names and plain values.

    Callers can only supply values, never operators: metadata keys must be simple
    identifiers and metadata values plain scalars (or lists of scalars). `start` and
    `end` are inclusive timestamp bounds. An exact `username` / `source_ip` takes
    precedence over the matching `*_present` flag.
    """
    query: dict[str, Any] = {}
    for name, value in (("event_type", event_type), ("status", status), ("action", action), ("source", source)):
        if value is not None:
            query[name] = _plain(value)

    for name, value, present in (("username", username, username_present), ("source_ip", source_ip, source_ip_present)):
        if value is not None:
            query[name] = value
        elif present:
            query[name] = {"$ne": None}

    for key, value in (metadata or {}).items():
        if not isinstance(key, str) or not _METADATA_KEY.match(key):
            raise ValueError("metadata filter keys must be simple identifiers")
        if isinstance(value, (list, tuple)):
            if not value or not all(isinstance(item, _SCALAR_TYPES) for item in value):
                raise ValueError("metadata filter lists must be non-empty and contain only plain values")
            query[f"metadata.{key}"] = {"$in": list(value)}
        elif isinstance(value, _SCALAR_TYPES):
            query[f"metadata.{key}"] = value
        else:
            raise ValueError("metadata filter values must be plain values")

    if start is not None or end is not None:
        bounds: dict[str, datetime] = {}
        if start is not None:
            bounds["$gte"] = start
        if end is not None:
            bounds["$lte"] = end
        query["timestamp"] = bounds
    return query
