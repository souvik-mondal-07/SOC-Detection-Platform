from app.core.errors import DatabaseUnavailableError


def test_generate_single(client, db, burst):
    r = client.post(f"/api/v1/alerts/generate/{burst[-1].event_id}")
    body = r.json()
    assert r.status_code == 200 and body["success"] and body["alerts_created"] == 1
    assert body["alerts"][0] == {"alert_id": body["alerts"][0]["alert_id"], "rule_id": "AUTH-001",
                                 "title": "Multiple Failed Logins Detected", "severity": "high", "status": "open"}


def test_generate_no_match(client, db, normal_event):
    body = client.post(f"/api/v1/alerts/generate/{normal_event.event_id}").json()
    assert body == {"success": True, "event_id": normal_event.event_id, "alerts_created": 0, "duplicates_skipped": 0, "alerts": []}


def test_generate_missing_event_404(client, db):
    r = client.post("/api/v1/alerts/generate/evt_missing")
    assert r.status_code == 404 and "Traceback" not in r.text


def test_generate_repeat_does_not_duplicate(client, db, burst):
    client.post(f"/api/v1/alerts/generate/{burst[-1].event_id}")
    body = client.post(f"/api/v1/alerts/generate/{burst[-1].event_id}").json()
    assert body["alerts_created"] == 0 and body["duplicates_skipped"] == 1


def test_batch(client, db, burst, normal_event):
    ids = [burst[-1].event_id, normal_event.event_id, "evt_missing"]
    body = client.post("/api/v1/alerts/generate", json={"event_ids": ids}).json()
    assert body["events_evaluated"] == 2 and body["alerts_created"] == 1
    assert body["failed_events"] == [{"event_id": "evt_missing", "error_code": "EVENT_NOT_FOUND", "message": "Event not found"}]


def test_batch_validation_and_client_cannot_set_fields(client, db):
    assert client.post("/api/v1/alerts/generate", json={"event_ids": []}).status_code == 422
    assert client.post("/api/v1/alerts/generate", json={"event_ids": ["evt_1"], "severity": "critical"}).status_code == 422


def test_list_get_filter_paginate(client, db, burst):
    client.post(f"/api/v1/alerts/generate/{burst[-1].event_id}")
    listing = client.get("/api/v1/alerts?severity=high&status=open").json()
    assert listing["count"] == 1 and listing["total"] == 1
    item = listing["alerts"][0]
    assert item["source_ip"] == "192.168.1.20" and "_id" not in item and "event_ids" not in item
    assert client.get("/api/v1/alerts?severity=low").json()["count"] == 0
    assert client.get("/api/v1/alerts?rule_id=AUTH-001&source_ip=192.168.1.20").json()["count"] == 1
    assert client.get("/api/v1/alerts?page=2&limit=1").json()["alerts"] == []
    detail = client.get(f"/api/v1/alerts/{item['alert_id']}").json()["alert"]
    assert set(detail["event_ids"]) == {e.event_id for e in burst}
    assert detail["created_at"] and detail["updated_at"] and "_id" not in detail


def test_list_validation(client, db):
    for query in ("limit=101", "limit=0", "page=0", "severity=urgent", "status=bogus", "source_ip=nope", "rule_id=bad"):
        assert client.get(f"/api/v1/alerts?{query}").status_code == 422, query


def test_get_missing_alert_404(client, db):
    r = client.get("/api/v1/alerts/ALT-20261007-999999")
    assert r.status_code == 404 and r.json() == {"error": {"message": "Alert not found"}}


def test_database_failure_503_without_details(client, db, monkeypatch):
    from app.repositories.alert_repository import AlertRepository

    def boom(*_a, **_k):
        raise DatabaseUnavailableError("mongodb://user:pw@host")
    monkeypatch.setattr(AlertRepository, "get_alerts", boom)
    r = client.get("/api/v1/alerts")
    assert r.status_code == 503 and "mongodb" not in r.text
