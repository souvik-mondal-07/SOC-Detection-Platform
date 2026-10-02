"""Shared MongoDB access for the four repositories.

Repositories hold all database operations. Routes and services never build
MongoDB queries themselves. Only the operations needed so far are implemented:
create, find_by_id, find_many and update. There is deliberately no delete.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, ClassVar, Generic, TypeVar

from pymongo import IndexModel
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from app.core.errors import DatabaseUnavailableError
from app.models.common import MongoModel, utc_now

ModelT = TypeVar("ModelT", bound=MongoModel)

MAX_PAGE_SIZE = 1000
_PROTECTED_FIELDS = {"created_at"}


class DuplicateRecordError(Exception):
    """A record with the same unique identifier already exists."""


@contextmanager
def translate_db_errors() -> Iterator[None]:
    """Turn driver connection failures into DatabaseUnavailableError."""
    try:
        yield
    except ConnectionFailure as exc:  # includes server-selection timeouts
        raise DatabaseUnavailableError("MongoDB is unreachable") from exc


class BaseRepository(Generic[ModelT]):
    model: ClassVar[type[Any]]
    collection_name: ClassVar[str]
    id_field: ClassVar[str]
    indexes: ClassVar[Sequence[IndexModel]] = ()

    def __init__(self, database: Database) -> None:
        self._collection = database[self.collection_name]

    def ensure_indexes(self) -> list[str]:
        """Create missing indexes. Idempotent and non-destructive."""
        with translate_db_errors():
            return self._collection.create_indexes(list(self.indexes))

    def create(self, item: ModelT) -> ModelT:
        try:
            with translate_db_errors():
                self._collection.insert_one(item.to_document())
        except DuplicateKeyError as exc:
            identifier = getattr(item, self.id_field)
            raise DuplicateRecordError(f"{self.id_field} '{identifier}' already exists") from exc
        return item

    def find_by_id(self, identifier: str) -> ModelT | None:
        with translate_db_errors():
            document = self._collection.find_one({self.id_field: identifier}, {"_id": 0})
        return self.model.from_document(document) if document else None

    def find_many(
        self,
        query: Mapping[str, Any] | None = None,
        *,
        sort: Sequence[tuple[str, int]] | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[ModelT]:
        """Return matching records. `query` must come from trusted code, not raw user input."""
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
        if skip < 0:
            raise ValueError("skip must be 0 or greater")
        with translate_db_errors():
            cursor = self._collection.find(dict(query or {}), {"_id": 0})
            if sort:
                cursor = cursor.sort(list(sort))
            documents = list(cursor.skip(skip).limit(limit))
        return [self.model.from_document(document) for document in documents]

    def update(self, identifier: str, changes: Mapping[str, Any]) -> ModelT | None:
        """Apply a partial update. The merged record is re-validated before saving,
        so invalid values (for example a bad status) can never be stored.
        Returns None if the record does not exist."""
        if not changes:
            raise ValueError("changes must not be empty")
        forbidden = ({self.id_field} | _PROTECTED_FIELDS) & set(changes)
        if forbidden:
            raise ValueError(f"fields cannot be changed: {sorted(forbidden)}")

        with translate_db_errors():
            existing = self._collection.find_one({self.id_field: identifier}, {"_id": 0})
        if existing is None:
            return None

        merged = {**existing, **changes}
        if "updated_at" in self.model.model_fields and "updated_at" not in changes:
            merged["updated_at"] = utc_now()
        updated = self.model.model_validate(merged)  # raises ValidationError if invalid

        document = updated.to_document()
        to_set = {k: v for k, v in document.items() if k in changes or k == "updated_at"}
        with translate_db_errors():
            self._collection.update_one({self.id_field: identifier}, {"$set": to_set})
        return updated
