"""Safe database initialization.

Creates the four collections and their indexes if they are missing. It never
drops, truncates or modifies existing data, and is safe to run repeatedly.

Run manually from the backend folder:  python -m app.repositories.initialization
"""

import logging
import sys

from pymongo.database import Database
from pymongo.errors import CollectionInvalid, PyMongoError

from app.core.database import check_connection, close_client, get_database
from app.core.errors import DatabaseUnavailableError
from app.repositories.alert_repository import AlertRepository
from app.repositories.base import BaseRepository, translate_db_errors
from app.repositories.detection_rule_repository import DetectionRuleRepository
from app.repositories.event_repository import EventRepository
from app.repositories.investigation_repository import InvestigationRepository

logger = logging.getLogger("soc.database")

REPOSITORY_CLASSES: tuple[type[BaseRepository], ...] = (
    EventRepository,
    AlertRepository,
    DetectionRuleRepository,
    InvestigationRepository,
)


def initialize_database(database: Database) -> dict[str, list[str]]:
    """Verify MongoDB is reachable, then ensure collections and indexes exist.

    Returns {collection_name: [index names]}. Raises DatabaseUnavailableError
    if MongoDB cannot be reached.
    """
    if not check_connection(database):
        raise DatabaseUnavailableError("MongoDB is unreachable")

    with translate_db_errors():
        existing = set(database.list_collection_names())
    result: dict[str, list[str]] = {}
    for repository_class in REPOSITORY_CLASSES:
        name = repository_class.collection_name
        if name not in existing:
            try:
                with translate_db_errors():
                    database.create_collection(name)
            except CollectionInvalid:
                pass  # created concurrently; fine
        result[name] = repository_class(database).ensure_indexes()
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = initialize_database(get_database())
    except (DatabaseUnavailableError, PyMongoError) as exc:
        print(f"Database initialization failed: {type(exc).__name__}. Is MongoDB running?", file=sys.stderr)
        return 1
    finally:
        close_client()
    for collection, indexes in result.items():
        print(f"{collection}: {len(indexes)} indexes ensured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
