"""MongoDB connection management.

One MongoClient is created lazily and reused for the whole process (the driver
manages its own connection pool). Creating the client does not contact the
server, so the application can start even when MongoDB is down.
"""

import logging
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import get_settings

logger = logging.getLogger("soc.database")

COLLECTION_EVENTS = "security_events"
COLLECTION_ALERTS = "alerts"
COLLECTION_RULES = "detection_rules"
COLLECTION_INVESTIGATIONS = "investigations"


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        tz_aware=True,  # datetimes read back are timezone-aware (UTC)
    )


def get_database() -> Database:
    """Return the configured database. Also used as a FastAPI dependency."""
    return get_client()[get_settings().mongodb_database]


def check_connection(database: Database) -> bool:
    """Return True if MongoDB answers a ping. Never raises, never logs the URI."""
    try:
        database.command("ping")
        return True
    except PyMongoError as exc:
        logger.warning("MongoDB ping failed (%s)", type(exc).__name__)
        return False


def close_client() -> None:
    """Close the shared client (called on application shutdown)."""
    if get_client.cache_info().currsize:
        get_client().close()
        get_client.cache_clear()
