import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.database import get_database
from app.main import app

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_logs"


def make_payload(**overrides):
    payload = {
        "timestamp": "2026-10-02T10:15:23Z",
        "source": "linux_auth",
        "event_type": "authentication",
        "action": "login",
        "status": "failed",
        "username": "test_user",
        "source_ip": "192.168.1.20",
        "message": "Failed password for test_user",
        "metadata": {},
    }
    return {**payload, **overrides}


def post_many(client, payloads):
    response = client.post("/api/v1/events/batch", json={"events": payloads})
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------ POST /events

def test_valid_event_accepted(client):
    response = client.post("/api/v1/events", json=make_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Security event ingested successfully"
    event = body["event"]
    assert event["event_id"].startswith("evt_")
    assert event["timestamp"] == "2026-10-02T10:15:23Z"
    assert (event["source"], event["event_type"], event["status"]) == ("linux_auth", "authentication", "failed")
    assert event["created_at"].endswith("Z")
    assert "_id" not in event and '"_id"' not in response.text


def test_event_is_actually_stored(client, mongo_db):
    event_id = client.post("/api/v1/events", json=make_payload()).json()["event"]["event_id"]
    stored = mongo_db["security_events"].find_one({"event_id": event_id})
    assert stored["username"] == "test_user" and stored["status"] == "failed"
    assert mongo_db["security_events"].count_documents({}) == 1


def test_generated_ids_are_random_and_unique(client):
    ids = [client.post("/api/v1/events", json=make_payload()).json()["event"]["event_id"] for _ in range(20)]
    assert len(set(ids)) == 20
    assert not any(i.removeprefix("evt_").isdigit() for i in ids)


@pytest.mark.parametrize("missing", ["source", "event_type", "action", "message"])
def test_missing_required_field_rejected(client, missing):
    payload = make_payload()
    del payload[missing]
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert f"body.{missing}" in fields


@pytest.mark.parametrize("timestamp", ["not-a-date", "2026-10-02T10:15:23", 1696243523, "1696243523", "2026-13-45T99:99:99Z"])
def test_invalid_timestamp_rejected(client, timestamp):
    response = client.post("/api/v1/events", json=make_payload(timestamp=timestamp))
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.timestamp"


@pytest.mark.parametrize("field,value", [
    ("event_type", "invalid_type"), ("status", "maybe"), ("source", "syslog"), ("source_ip", "999.1.1.1"),
])
def test_invalid_values_rejected(client, field, value):
    response = client.post("/api/v1/events", json=make_payload(**{field: value}))
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == f"body.{field}"


def test_unknown_and_server_controlled_fields_rejected(client):
    for extra in ({"event_id": "evt_mine"}, {"created_at": "2026-01-01T00:00:00Z"}, {"password": "x"}):
        assert client.post("/api/v1/events", json=make_payload(**extra)).status_code == 422


def test_normalisation_applied_through_api(client):
    body = client.post("/api/v1/events", json=make_payload(status="FAILED", event_type="AUTH", source="Linux Auth")).json()
    assert (body["event"]["status"], body["event"]["event_type"], body["event"]["source"]) == ("failed", "authentication", "linux_auth")


def test_timestamp_offset_converted_to_utc(client):
    event = client.post("/api/v1/events", json=make_payload(timestamp="2026-10-02T12:15:23+02:00")).json()["event"]
    assert event["timestamp"] == "2026-10-02T10:15:23Z"


def test_missing_timestamp_is_generated_and_flagged(client):
    payload = make_payload()
    del payload["timestamp"]
    event = client.post("/api/v1/events", json=payload).json()["event"]
    assert event["timestamp"].endswith("Z")
    assert event["metadata"]["timestamp_generated"] is True


def test_missing_status_defaults_to_unknown_and_blocked_is_accepted(client):
    payload = make_payload()
    del payload["status"]
    assert client.post("/api/v1/events", json=payload).json()["event"]["status"] == "unknown"
    assert client.post("/api/v1/events", json=make_payload(status="blocked")).json()["event"]["status"] == "blocked"


def test_new_source_and_event_types_accepted(client):
    for source in ("windows_event", "web_application", "network", "application"):
        assert client.post("/api/v1/events", json=make_payload(source=source)).status_code == 201
    for event_type in ("web", "network", "privilege", "system", "application"):
        assert client.post("/api/v1/events", json=make_payload(event_type=event_type)).status_code == 201


def test_secret_like_metadata_rejected_without_echoing_value(client):
    response = client.post("/api/v1/events", json=make_payload(metadata={"password": "SuperSecret123"}))
    assert response.status_code == 422
    assert "SuperSecret123" not in response.text


def test_malformed_body_rejected(client):
    assert client.post("/api/v1/events", content="{not json", headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/v1/events", json=[]).status_code == 422


def test_database_failure_returns_clean_503():
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    app.dependency_overrides[get_database] = lambda: dead["soc_test"]
    try:
        response = TestClient(app).post("/api/v1/events", json=make_payload())
    finally:
        app.dependency_overrides.clear()
        dead.close()
    assert response.status_code == 503
    assert response.json() == {"error": {"message": "Database is unavailable"}}
    assert "mongodb" not in response.text.lower() and "127.0.0.1" not in response.text


# ------------------------------------------------------------ GET /events

@pytest.fixture
def seeded(client):
    post_many(client, [
        make_payload(timestamp="2026-10-02T10:00:00Z", status="failed", source_ip="192.168.1.20"),
        make_payload(timestamp="2026-10-02T10:01:00Z", status="success", source_ip="192.168.1.20"),
        make_payload(timestamp="2026-10-02T10:02:00Z", source="network", event_type="network", action="connection",
                     status="blocked", username=None, source_ip="192.168.1.60", message="blocked"),
        make_payload(timestamp="2026-10-02T10:03:00Z", source="web_application", event_type="web", action="get_request",
                     status="failed", username=None, source_ip="192.168.1.41", message="GET /x 404"),
    ])


def test_events_returned_newest_first(client, seeded):
    body = client.get("/api/v1/events").json()
    assert body["count"] == 4
    assert [e["timestamp"] for e in body["events"]] == sorted((e["timestamp"] for e in body["events"]), reverse=True)


def test_limit_works(client, seeded):
    assert client.get("/api/v1/events?limit=2").json()["count"] == 2


@pytest.mark.parametrize("limit", [0, -1, 501, "abc"])
def test_invalid_limit_rejected(client, limit):
    assert client.get(f"/api/v1/events?limit={limit}").status_code == 422


def test_filter_by_event_type(client, seeded):
    body = client.get("/api/v1/events?event_type=authentication&limit=20").json()
    assert body["count"] == 2 and {e["event_type"] for e in body["events"]} == {"authentication"}


def test_filter_by_source(client, seeded):
    body = client.get("/api/v1/events?source=network").json()
    assert [e["source"] for e in body["events"]] == ["network"]


def test_filter_by_status(client, seeded):
    body = client.get("/api/v1/events?status=failed").json()
    assert body["count"] == 2 and {e["status"] for e in body["events"]} == {"failed"}


def test_filter_by_source_ip_and_combined_filters(client, seeded):
    assert client.get("/api/v1/events?source_ip=192.168.1.20").json()["count"] == 2
    assert client.get("/api/v1/events?source_ip=192.168.1.20&status=success").json()["count"] == 1


def test_filter_values_are_normalised(client, seeded):
    assert client.get("/api/v1/events?status=FAILED&event_type=AUTH").json()["count"] == 1


def test_invalid_filter_value_or_unknown_parameter_rejected(client, seeded):
    assert client.get("/api/v1/events?status=banana").status_code == 422
    assert client.get("/api/v1/events?source_ip=nope").status_code == 422
    assert client.get("/api/v1/events?severity=high").status_code == 422


def test_filter_cannot_inject_query_operators(client, seeded):
    assert client.get("/api/v1/events?source_ip[$ne]=x").status_code == 422


def test_no_matches_returns_empty_list(client, seeded):
    assert client.get("/api/v1/events?source_ip=10.9.9.9").json() == {"count": 0, "events": []}


# ------------------------------------------------------------ GET /events/{id}

def test_existing_event_returned(client):
    created = client.post("/api/v1/events", json=make_payload()).json()["event"]
    response = client.get(f"/api/v1/events/{created['event_id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_unknown_event_returns_404(client):
    response = client.get("/api/v1/events/evt_doesnotexist")
    assert response.status_code == 404
    assert response.json() == {"error": {"message": "Event not found"}}


def test_event_id_is_not_treated_as_a_query(client):
    assert client.get("/api/v1/events/%7B%22%24ne%22%3A1%7D").status_code == 404


# ------------------------------------------------------------ POST /events/batch

def test_batch_all_valid(client, mongo_db):
    body = post_many(client, [make_payload(), make_payload(status="success"), make_payload(source="network", event_type="net")])
    assert body["success"] is True and body["accepted"] == 3 and body["rejected"] == 0
    assert len(set(body["event_ids"])) == 3 and body["errors"] == []
    assert mongo_db["security_events"].count_documents({}) == 3


def test_batch_partial_success_stores_valid_events_and_reports_invalid(client, mongo_db):
    payloads = [
        make_payload(),
        make_payload(event_type="nope"),
        "not an object",
        make_payload(timestamp="bad"),
        make_payload(status="blocked"),
    ]
    response = client.post("/api/v1/events/batch", json={"events": payloads})
    assert response.status_code == 201
    body = response.json()
    assert (body["success"], body["accepted"], body["rejected"]) == (False, 2, 3)
    assert [e["index"] for e in body["errors"]] == [1, 2, 3]
    assert body["errors"][0]["errors"][0]["field"] == "event_type"
    assert body["errors"][1]["errors"][0]["message"] == "Each event must be a JSON object"
    assert mongo_db["security_events"].count_documents({}) == 2  # only the valid ones


def test_batch_event_ids_returned_in_submission_order(client):
    body = post_many(client, [make_payload(message=f"m{i}") for i in range(3)])
    for index, event_id in enumerate(body["event_ids"]):
        assert client.get(f"/api/v1/events/{event_id}").json()["message"] == f"m{index}"


def test_batch_all_invalid_returns_422_and_stores_nothing(client, mongo_db):
    response = client.post("/api/v1/events/batch", json={"events": [make_payload(status="x"), {}]})
    assert response.status_code == 422
    body = response.json()
    assert (body["accepted"], body["rejected"]) == (0, 2)
    assert mongo_db["security_events"].count_documents({}) == 0


def test_batch_errors_do_not_echo_secret_values(client):
    response = client.post("/api/v1/events/batch", json={"events": [make_payload(metadata={"api_key": "TopSecretValue"})]})
    assert "TopSecretValue" not in response.text


def test_batch_size_limits(client):
    assert client.post("/api/v1/events/batch", json={"events": []}).status_code == 422
    assert client.post("/api/v1/events/batch", json={"events": [make_payload()] * 501}).status_code == 422
    assert client.post("/api/v1/events/batch", json={"events": "x"}).status_code == 422


# ------------------------------------------------------------ sample files

@pytest.mark.parametrize("name", ["normal_auth", "failed_auth", "web_events", "network_events"])
def test_every_sample_file_ingests_cleanly(client, name):
    events = json.loads((SAMPLE_DIR / f"{name}.json").read_text())
    assert 1 <= len(events) <= 20  # kept small
    body = post_many(client, events)
    assert body["accepted"] == len(events) and body["rejected"] == 0


def test_sample_data_is_synthetic_and_local():
    import ipaddress

    for name in ["normal_auth", "failed_auth", "web_events", "network_events"]:
        for event in json.loads((SAMPLE_DIR / f"{name}.json").read_text()):
            assert event["metadata"]["synthetic"] is True
            assert ipaddress.ip_address(event["source_ip"]).is_private
            assert event.get("username", "test_user") in {"test_user", "demo_user", "unknown_user_1", "unknown_user_2"}
