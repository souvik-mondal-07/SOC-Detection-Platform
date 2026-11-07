import re
from datetime import datetime

from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.database import COLLECTION_INVESTIGATIONS
from app.models.common import utc_now
from app.models.investigation import Investigation, InvestigationNote
from app.repositories.base import BaseRepository, translate_db_errors

MAX_INVESTIGATION_PAGE_LIMIT = 100


class InvestigationRepository(BaseRepository[Investigation]):
    model = Investigation
    collection_name = COLLECTION_INVESTIGATIONS
    id_field = "investigation_id"
    indexes = (
        IndexModel([("investigation_id", ASCENDING)], name="uq_investigation_id", unique=True),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="ix_status_created_at"),  # open investigations
        IndexModel([("created_at", DESCENDING)], name="ix_created_at"),  # newest first
        # Step 11: "which investigations include this alert?" (multikey index on the alert_ids array)
        IndexModel([("alert_ids", ASCENDING)], name="ix_alert_ids"),
    )

    def create_investigation(self, investigation: Investigation) -> Investigation:
        """Insert. Raises DuplicateRecordError if the investigation_id already exists."""
        return self.create(investigation)

    def get_investigation_by_id(self, investigation_id: str) -> Investigation | None:
        return self.find_by_id(investigation_id)

    def get_investigations(
        self,
        *,
        status: str | None = None,
        alert_id: str | None = None,
        title_contains: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Investigation], int]:
        """One page of investigations, newest first, plus the total matching the filters.

        The query is built here from fixed fields; client text only ever becomes a value
        (the title search is an escaped, case-insensitive substring match).
        """
        if not 1 <= limit <= MAX_INVESTIGATION_PAGE_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_INVESTIGATION_PAGE_LIMIT}")
        if skip < 0:
            raise ValueError("skip must be 0 or greater")
        query: dict = {}
        if status is not None:
            query["status"] = status
        if alert_id is not None:
            query["alert_ids"] = alert_id
        if title_contains:
            query["title"] = {"$regex": re.escape(title_contains), "$options": "i"}
        with translate_db_errors():
            total = self._collection.count_documents(query)
            cursor = (
                self._collection.find(query, {"_id": 0})
                .sort([("created_at", DESCENDING), ("investigation_id", DESCENDING)])
                .skip(skip)
                .limit(limit)
            )
            documents = list(cursor)
        return [Investigation.from_document(document) for document in documents], total

    def next_investigation_id(self, now: datetime) -> str:
        """Next readable ID for `now`'s UTC day, e.g. INV-20261014-000001.

        Two writers can pick the same number; the unique index rejects one and the caller retries.
        """
        prefix = f"INV-{now:%Y%m%d}-"
        with translate_db_errors():
            latest = self._collection.find_one(
                {"investigation_id": {"$regex": f"^{re.escape(prefix)}"}},
                {"_id": 0, "investigation_id": 1},
                sort=[("investigation_id", DESCENDING)],
            )
        number = 1
        if latest:
            try:
                number = int(latest["investigation_id"][len(prefix):]) + 1
            except ValueError:
                number = 1
        return f"{prefix}{number:06d}"

    # -- atomic single-field operations (one MongoDB update each, so concurrent edits do not overwrite each other) --

    def add_alert_ids(self, investigation_id: str, alert_ids: list[str]) -> bool:
        """Add alert IDs ($addToSet, so a duplicate can never be stored). False if the investigation does not exist."""
        with translate_db_errors():
            result = self._collection.update_one(
                {"investigation_id": investigation_id},
                {"$addToSet": {"alert_ids": {"$each": list(dict.fromkeys(alert_ids))}}, "$set": {"updated_at": utc_now()}},
            )
        return result.matched_count == 1

    def remove_alert_id(self, investigation_id: str, alert_id: str) -> bool:
        """Remove one alert ID, but only if it is linked and is not the last one.

        Returns False if nothing changed (not linked, last alert, or no such investigation).
        """
        with translate_db_errors():
            result = self._collection.update_one(
                {"investigation_id": investigation_id, "alert_ids": alert_id, "alert_ids.1": {"$exists": True}},
                {"$pull": {"alert_ids": alert_id}, "$set": {"updated_at": utc_now()}},
            )
        return result.modified_count == 1

    def add_note(self, investigation_id: str, note: InvestigationNote) -> bool:
        """Append a note. False if the investigation does not exist."""
        with translate_db_errors():
            result = self._collection.update_one(
                {"investigation_id": investigation_id},
                {"$push": {"notes": note.to_document()}, "$set": {"updated_at": utc_now()}},
            )
        return result.matched_count == 1
