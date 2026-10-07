import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.database import get_database
from app.main import app
from tests.parsers.conftest import raw_json, raw_lines

URL = "/api/v1/events/parse"
LINUX_FAIL = "Oct  2 10:15:23 server sshd[1234]: Failed password for test_user from 192.168.1.20 port 54321 ssh2"
LINUX_OK = "Oct  2 10:17:12 server sshd[1234]: Accepted password for test_user from 192.168.1.20 port 54321 ssh2"


def test_successful_parse_is_stored(client, mongo_db):
    response = client.post(URL, json={"source_type": "linux_auth", "raw_log": LINUX_FAIL})
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True and body["message"] == "Log parsed and security event ingested successfully"
    event = body["event"]
    assert event["event_id"].startswith("evt_")
    assert (event["source"], event["event_type"], event["action"], event["status"]) == ("linux_auth", "authentication", "login", "failed")
    assert (event["username"], event["source_ip"]) == ("test_user", "192.168.1.20")
    assert event["timestamp"].endswith("T10:15:23Z")
    stored = mongo_db["security_events"].find_one({"event_id": event["event_id"]})
    assert stored["source_ip"] == "192.168.1.20" and "_id" not in event and '"_id"' not in response.text


def test_parsed_event_readable_through_step4_api(client):
    event_id = client.post(URL, json={"source_type": "linux_auth", "raw_log": LINUX_FAIL}).json()["event"]["event_id"]
    assert client.get(f"/api/v1/events/{event_id}").json()["username"] == "test_user"
    assert client.get("/api/v1/events", params={"source": "linux_auth"}).json()["count"] == 1


def test_each_format_through_the_api(client):
    web = client.post(URL, json={"source_type": "web_application", "raw_log": raw_lines("web_access.log")[0]})
    win = client.post(URL, json={"source_type": "windows_event", "raw_log": raw_json("windows_events.json")[0]})
    net = client.post(URL, json={"source_type": "network", "raw_log": raw_json("network_events.json")[0]})
    assert [r.status_code for r in (web, win, net)] == [201, 201, 201]
    assert web.json()["event"]["metadata"]["path"] == "/admin"
    assert win.json()["event"]["metadata"]["event_id"] == 4625
    assert net.json()["event"]["metadata"]["destination_port"] == 22


def test_unsupported_source_type(client, mongo_db):
    response = client.post(URL, json={"source_type": "firewall", "raw_log": "x"})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "unsupported_source_type" and "linux_auth" in error["message"]
    assert mongo_db["security_events"].count_documents({}) == 0


def test_invalid_log_returns_structured_error_without_echoing_input(client, mongo_db):
    secret = "hunter2-not-a-real-secret"
    response = client.post(URL, json={"source_type": "linux_auth", "raw_log": f"garbage {secret}"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_log"
    assert secret not in response.text
    assert mongo_db["security_events"].count_documents({}) == 0


def test_parsed_but_schema_invalid_event_is_rejected_with_details(client):
    bad_ip = "Oct  2 10:15:23 server sshd[1]: Failed password for u from 999.1.1.1 port 1 ssh2"
    response = client.post(URL, json={"source_type": "linux_auth", "raw_log": bad_ip})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed" and error["details"][0]["field"] == "source_ip"


def test_unsupported_windows_event_id(client):
    response = client.post(URL, json={"source_type": "windows_event", "raw_log": {"EventID": 1}})
    assert response.status_code == 422 and response.json()["error"]["code"] == "unsupported_event"


@pytest.mark.parametrize("body", [
    {},
    {"source_type": "linux_auth"},
    {"raw_log": LINUX_FAIL},
    {"source_type": "linux_auth", "raw_log": 42},
    {"source_type": "linux_auth", "raw_log": None},
    {"source_type": "linux_auth", "raw_log": LINUX_FAIL, "extra": 1},
    [],
])
def test_malformed_request_body(client, body):
    assert client.post(URL, json=body).status_code == 422


def test_malformed_json(client):
    assert client.post(URL, content="{nope", headers={"Content-Type": "application/json"}).status_code == 422


def test_database_failure_returns_clean_503():
    dead = MongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    app.dependency_overrides[get_database] = lambda: dead["soc_test"]
    try:
        single = TestClient(app).post(URL, json={"source_type": "linux_auth", "raw_log": LINUX_FAIL})
        batch = TestClient(app).post(URL + "/batch", json={"source_type": "linux_auth", "logs": [LINUX_FAIL]})
    finally:
        app.dependency_overrides.clear()
        dead.close()
    for response in (single, batch):
        assert response.status_code == 503
        assert response.json() == {"error": {"message": "Database is unavailable"}}
        assert "mongodb" not in response.text.lower() and "127.0.0.1" not in response.text


# ---------------------------------------------------------------- batch

def test_batch_all_valid(client, mongo_db):
    response = client.post(URL + "/batch", json={"source_type": "linux_auth", "logs": [LINUX_FAIL, LINUX_OK]})
    assert response.status_code == 201
    body = response.json()
    assert (body["success"], body["total"], body["accepted"], body["rejected"], body["errors"]) == (True, 2, 2, 0, [])
    assert len(set(body["event_ids"])) == 2
    assert mongo_db["security_events"].count_documents({}) == 2


def test_batch_mixed_valid_and_invalid(client, mongo_db):
    logs = [LINUX_FAIL, "this is not a valid authentication log", LINUX_OK, None, 7]
    response = client.post(URL + "/batch", json={"source_type": "linux_auth", "logs": logs})
    assert response.status_code == 201
    body = response.json()
    assert (body["success"], body["total"], body["accepted"], body["rejected"]) == (False, 5, 2, 3)
    assert [e["index"] for e in body["errors"]] == [1, 3, 4]
    assert all(e["code"] == "invalid_log" for e in body["errors"])
    assert mongo_db["security_events"].count_documents({}) == 2


def test_batch_all_invalid_returns_422_and_stores_nothing(client, mongo_db):
    response = client.post(URL + "/batch", json={"source_type": "linux_auth", "logs": ["bad", "worse"]})
    assert response.status_code == 422
    assert response.json()["accepted"] == 0 and response.json()["rejected"] == 2
    assert mongo_db["security_events"].count_documents({}) == 0


def test_batch_of_json_objects(client):
    response = client.post(URL + "/batch", json={"source_type": "windows_event", "logs": raw_json("windows_events.json")})
    assert response.status_code == 201 and response.json()["accepted"] == 4


def test_batch_schema_validation_error_is_per_item(client):
    logs = [LINUX_FAIL, "Oct  2 10:15:23 server sshd[1]: Failed password for u from 999.1.1.1 port 1 ssh2"]
    body = client.post(URL + "/batch", json={"source_type": "linux_auth", "logs": logs}).json()
    assert body["accepted"] == 1 and body["errors"][0]["index"] == 1
    assert body["errors"][0]["details"][0]["field"] == "source_ip"


def test_batch_unsupported_source_type(client):
    response = client.post(URL + "/batch", json={"source_type": "firewall", "logs": ["x"]})
    assert response.status_code == 400 and response.json()["error"]["code"] == "unsupported_source_type"


@pytest.mark.parametrize("body", [
    {"source_type": "linux_auth", "logs": []},
    {"source_type": "linux_auth"},
    {"source_type": "linux_auth", "logs": "not a list"},
    {"source_type": "linux_auth", "logs": ["x"] * 501},
])
def test_batch_malformed_request(client, body):
    assert client.post(URL + "/batch", json=body).status_code == 422


def test_step4_endpoints_still_work(client):
    payload = {"source": "linux_auth", "event_type": "authentication", "action": "login", "status": "failed", "message": "m"}
    assert client.post("/api/v1/events", json=payload).status_code == 201
    assert client.post("/api/v1/events/batch", json={"events": [payload]}).status_code == 201
    assert client.get("/api/v1/health").status_code == 200
