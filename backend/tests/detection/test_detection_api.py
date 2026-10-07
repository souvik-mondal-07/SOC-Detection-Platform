"""POST /api/v1/detection/evaluate[/{event_id}] end to end (ingest through the API, then evaluate)."""

import pytest

from tests.detection.conftest import at, seed_module  # noqa: F401  (fixture)


@pytest.fixture
def seeded_client(client, mongo_db, seed_module):  # noqa: F811
    seed_module.seed(mongo_db)
    return client


def ingest(client, seconds, **overrides) -> str:
    body = {"timestamp": at(seconds).isoformat().replace("+00:00", "Z"), "source": "linux_auth", "event_type": "authentication",
            "action": "login", "status": "failed", "username": "test_user", "source_ip": "192.168.1.20",
            "message": "Failed password for test_user", **overrides}
    response = client.post("/api/v1/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()["event"]["event_id"]


def test_five_failures_match_auth001(seeded_client):
    ids = [ingest(seeded_client, i * 20) for i in range(5)]
    response = seeded_client.post(f"/api/v1/detection/evaluate/{ids[-1]}")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True and body["event_id"] == ids[-1]
    assert [m["rule_id"] for m in body["matches"]] == ["AUTH-001"]
    match = body["matches"][0]
    assert match["matched"] is True and match["severity"] == "high"
    assert match["reason"] == "5 failed authentication events from the same source IP within 5 minutes"


def test_four_failures_no_match(seeded_client):
    ids = [ingest(seeded_client, i * 20) for i in range(4)]
    body = seeded_client.post(f"/api/v1/detection/evaluate/{ids[-1]}").json()
    assert body["success"] is True and body["matches"] == []


def test_different_ips_and_outside_window(seeded_client):
    a = [ingest(seeded_client, i, source_ip="192.168.1.20") for i in range(3)]
    b = [ingest(seeded_client, i, source_ip="192.168.1.50") for i in range(2)]
    assert seeded_client.post(f"/api/v1/detection/evaluate/{a[-1]}").json()["matches"] == []
    assert seeded_client.post(f"/api/v1/detection/evaluate/{b[-1]}").json()["matches"] == []
    slow = [ingest(seeded_client, 1000 + i * 100, source_ip="10.0.0.5") for i in range(5)]  # 400 s apart overall
    assert seeded_client.post(f"/api/v1/detection/evaluate/{slow[-1]}").json()["matches"] == []


def test_unknown_event_is_404(seeded_client):
    response = seeded_client.post("/api/v1/detection/evaluate/evt_doesnotexist")
    assert response.status_code == 404
    assert response.json() == {"error": {"message": "Event not found"}}


def test_invalid_event_id_is_rejected(seeded_client):
    assert seeded_client.post("/api/v1/detection/evaluate/bad%20id").status_code == 422


def test_batch_evaluation(seeded_client):
    ids = [ingest(seeded_client, i * 20) for i in range(5)]
    benign = ingest(seeded_client, 0, status="success", source_ip="10.7.7.7")
    response = seeded_client.post("/api/v1/detection/evaluate", json={"event_ids": [*ids, benign, "evt_missing"]})
    assert response.status_code == 200
    body = response.json()
    assert body["events_evaluated"] == 6 and body["total_matches"] == 5
    assert body["not_found_event_ids"] == ["evt_missing"]
    assert len(body["results"]) == 6
    assert next(r for r in body["results"] if r["event_id"] == benign)["matches"] == []


@pytest.mark.parametrize("payload", [{}, {"event_ids": []}, {"event_ids": ["evt_1"] * 501}, {"event_ids": ["bad id"]},
                                     {"event_ids": ["evt_1"], "extra": 1}, {"event_ids": "evt_1"}])
def test_batch_request_validation(seeded_client, payload):
    assert seeded_client.post("/api/v1/detection/evaluate", json=payload).status_code == 422


def test_evaluation_never_creates_alerts_or_events(seeded_client, mongo_db):
    ids = [ingest(seeded_client, i * 20) for i in range(5)]
    events_before = mongo_db["security_events"].count_documents({})
    seeded_client.post(f"/api/v1/detection/evaluate/{ids[0]}")
    seeded_client.post("/api/v1/detection/evaluate", json={"event_ids": ids})
    assert mongo_db["alerts"].count_documents({}) == 0
    assert mongo_db["security_events"].count_documents({}) == events_before


def test_invalid_stored_rule_is_reported_not_fatal(seeded_client, mongo_db):
    mongo_db["detection_rules"].update_one({"rule_id": "WEB-001"}, {"$set": {"conditions": {"event_type": "web", "stages": []}}})
    ids = [ingest(seeded_client, i * 20) for i in range(5)]
    body = seeded_client.post(f"/api/v1/detection/evaluate/{ids[-1]}").json()
    assert body["skipped_rule_ids"] == ["WEB-001"] and [m["rule_id"] for m in body["matches"]] == ["AUTH-001"]


def test_parsed_linux_logs_trigger_auth002_via_the_parser(seeded_client):
    """End to end with Step 5: a real sshd 'invalid user' line, parsed and stored, matches AUTH-002."""
    response = seeded_client.post("/api/v1/events/parse", json={
        "source_type": "linux_auth",
        "raw_log": "2026-10-02T10:00:00+00:00 host sshd[1]: Failed password for invalid user ghost from 203.0.113.7 port 22 ssh2"})
    assert response.status_code in (200, 201), response.text
    event_id = response.json()["event"]["event_id"]
    matches = seeded_client.post(f"/api/v1/detection/evaluate/{event_id}").json()["matches"]
    assert "AUTH-002" in {m["rule_id"] for m in matches}
