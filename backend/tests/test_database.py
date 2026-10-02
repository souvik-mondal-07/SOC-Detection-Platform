import pytest
from pymongo import MongoClient

from app.core.database import check_connection, close_client, get_client, get_database
from app.core.errors import DatabaseUnavailableError
from app.repositories.event_repository import EventRepository
from app.repositories.initialization import REPOSITORY_CLASSES, initialize_database


def test_check_connection_true_when_reachable(mongo_db):
    assert check_connection(mongo_db) is True


def test_check_connection_false_when_unreachable():
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    try:
        assert check_connection(dead["soc_test"]) is False
    finally:
        dead.close()


def test_single_shared_client_is_reused():
    # Creating the client is lazy, so no MongoDB server is needed here.
    try:
        assert get_client() is get_client()
        assert get_database().name == "soc_detection_platform"
    finally:
        close_client()


def test_initialize_creates_collections_and_indexes(mongo_db):
    result = initialize_database(mongo_db)
    assert set(result) == {"security_events", "alerts", "detection_rules", "investigations"}
    assert set(mongo_db.list_collection_names()) == set(result)
    assert "uq_event_id" in mongo_db["security_events"].index_information()


def test_initialize_is_idempotent_and_keeps_existing_data(mongo_db):
    initialize_database(mongo_db)
    mongo_db["security_events"].insert_one({"event_id": "keep_me"})
    initialize_database(mongo_db)  # second run must not delete or fail
    assert mongo_db["security_events"].count_documents({"event_id": "keep_me"}) == 1


def test_initialize_raises_when_database_unavailable():
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    try:
        with pytest.raises(DatabaseUnavailableError):
            initialize_database(dead["soc_test"])
    finally:
        dead.close()


def test_repository_operations_raise_clean_error_when_unavailable():
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    try:
        with pytest.raises(DatabaseUnavailableError):
            EventRepository(dead["soc_test"]).find_by_id("evt_001")
    finally:
        dead.close()


def test_every_repository_defines_a_unique_id_index():
    for repository_class in REPOSITORY_CLASSES:
        unique = [i for i in repository_class.indexes if i.document.get("unique")]
        assert len(unique) == 1
        assert list(unique[0].document["key"].keys()) == [repository_class.id_field]
