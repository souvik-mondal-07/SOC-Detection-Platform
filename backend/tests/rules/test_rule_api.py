"""HTTP-level tests for /api/v1/rules, including detection integration."""

import pytest

from tests.detection.conftest import make
from tests.rules.conftest import rule_payload

URL = "/api/v1/rules"


@pytest.fixture
def api(client, seeded):
    return client


def error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == code
    assert body["message"]
    return body


# -- list / filter / paginate ---------------------------------------------------------------

def test_list_all_seeded_rules(api):
    body = api.get(URL).json()
    assert body["success"] is True
    assert (body["total"], body["count"], body["page"], body["limit"]) == (5, 5, 1, 20)
    assert [r["rule_id"] for r in body["rules"]] == ["AUTH-001", "AUTH-002", "AUTH-003", "NET-001", "WEB-001"]
    assert set(body["rules"][0]) == {"rule_id", "name", "category", "severity", "enabled"}
    assert '"_id"' not in api.get(URL).text


@pytest.mark.parametrize("query,expected", [
    ("category=authentication", ["AUTH-001", "AUTH-002", "AUTH-003"]),
    ("severity=medium", ["AUTH-002", "NET-001", "WEB-001"]),
    ("severity=high", ["AUTH-001", "AUTH-003"]),
    ("enabled=true", ["AUTH-001", "AUTH-002", "AUTH-003", "NET-001", "WEB-001"]),
    ("enabled=false", []),
    ("category=authentication&severity=high&enabled=true", ["AUTH-001", "AUTH-003"]),
    ("category=web&severity=high", []),
    ("name=failed", ["AUTH-001", "AUTH-003"]),
])
def test_list_filters(api, query, expected):
    body = api.get(f"{URL}?{query}").json()
    assert [r["rule_id"] for r in body["rules"]] == expected
    assert body["total"] == len(expected)


def test_filter_enabled_false_after_disable(api):
    api.patch(f"{URL}/WEB-001/status", json={"enabled": False})
    assert [r["rule_id"] for r in api.get(f"{URL}?enabled=false").json()["rules"]] == ["WEB-001"]


def test_pagination(api):
    first = api.get(f"{URL}?page=1&limit=2").json()
    assert [r["rule_id"] for r in first["rules"]] == ["AUTH-001", "AUTH-002"]
    assert (first["total"], first["count"], first["page"], first["limit"]) == (5, 2, 1, 2)
    last = api.get(f"{URL}?page=3&limit=2").json()
    assert [r["rule_id"] for r in last["rules"]] == ["WEB-001"]
    assert api.get(f"{URL}?page=10&limit=2").json()["rules"] == []


def test_limit_maximum(api):
    assert api.get(f"{URL}?limit=100").status_code == 200
    error(api.get(f"{URL}?limit=101"), 422, "INVALID_RULE")
    error(api.get(f"{URL}?limit=0"), 422, "INVALID_RULE")
    error(api.get(f"{URL}?page=0"), 422, "INVALID_RULE")


def test_invalid_filter_values(api):
    error(api.get(f"{URL}?severity=urgent"), 422, "INVALID_SEVERITY")
    error(api.get(f"{URL}?category=astrology"), 422, "INVALID_CATEGORY")
    error(api.get(f"{URL}?enabled=maybe"), 422, "INVALID_STATUS")


# -- get ------------------------------------------------------------------------------------

def test_get_rule(api):
    body = api.get(f"{URL}/AUTH-001").json()
    assert body["success"] is True
    rule = body["rule"]
    assert rule["conditions"]["threshold"] == 5
    assert {"description", "created_at", "updated_at", "conditions"} <= set(rule)


def test_get_missing_rule(api):
    error(api.get(f"{URL}/NOPE-001"), 404, "RULE_NOT_FOUND")


# -- create ---------------------------------------------------------------------------------

def test_create_rule(api):
    response = api.post(URL, json=rule_payload())
    assert response.status_code == 201
    rule = response.json()["rule"]
    assert rule["rule_id"] == "AUTH-004" and rule["enabled"] is True
    assert api.get(f"{URL}/AUTH-004").status_code == 200


def test_create_duplicate(api):
    assert api.post(URL, json=rule_payload()).status_code == 201
    error(api.post(URL, json=rule_payload()), 409, "RULE_ALREADY_EXISTS")
    error(api.post(URL, json=rule_payload(rule_id="AUTH-001")), 409, "RULE_ALREADY_EXISTS")


def test_create_validation_errors(api):
    data = rule_payload()
    del data["name"]
    error(api.post(URL, json=data), 422, "INVALID_RULE")
    error(api.post(URL, json=rule_payload(name="")), 422, "INVALID_RULE")
    error(api.post(URL, json=rule_payload(rule_id="bad id")), 422, "INVALID_RULE")
    error(api.post(URL, json=rule_payload(category="astrology")), 422, "INVALID_CATEGORY")
    for bad in ("urgent", "danger", "severe"):
        error(api.post(URL, json=rule_payload(severity=bad)), 422, "INVALID_SEVERITY")
    error(api.post(URL, json=rule_payload(enabled="yes")), 422, "INVALID_STATUS")
    error(api.post(URL, json=rule_payload(conditions="not an object")), 422, "INVALID_CONDITION")
    error(api.post(URL, json=rule_payload(conditions={"event_type": "authentication", "threshold": 0, "window_minutes": 5})), 422, "INVALID_CONDITION")
    error(api.post(URL, json=rule_payload(conditions={"event_type": "authentication", "code": "__import__('os')"})), 422, "INVALID_CONDITION")
    error(api.post(URL, json=rule_payload(created_at="2001-01-01T00:00:00Z")), 422, "INVALID_RULE")
    assert api.get(f"{URL}/AUTH-004").status_code == 404  # nothing stored by failed attempts


def test_malformed_json_uses_error_format(api):
    error(api.post(URL, content="{not json", headers={"content-type": "application/json"}), 422, "INVALID_RULE")


def test_errors_do_not_echo_values_or_internals(api):
    secret = "S3cretValue_do_not_echo"
    response = api.post(URL, json=rule_payload(severity=secret, name=secret))
    assert secret not in response.text
    for leak in ("Traceback", "mongodb://", "pymongo"):
        assert leak not in response.text


# -- update ---------------------------------------------------------------------------------

def test_update_rule(api):
    before = api.get(f"{URL}/AUTH-001").json()["rule"]
    response = api.put(f"{URL}/AUTH-001", json={
        "name": "Failed Logins (tuned)", "severity": "critical",
        "conditions": {"event_type": "authentication", "status": "failed", "threshold": 8, "window_minutes": 5},
    })
    assert response.status_code == 200
    rule = response.json()["rule"]
    assert rule["name"] == "Failed Logins (tuned)" and rule["severity"] == "critical"
    assert rule["conditions"]["threshold"] == 8
    assert rule["created_at"] == before["created_at"]
    assert rule["updated_at"] >= before["updated_at"]


def test_update_invalid_and_missing(api):
    error(api.put(f"{URL}/AUTH-001", json={"severity": "urgent"}), 422, "INVALID_SEVERITY")
    error(api.put(f"{URL}/AUTH-001", json={"category": "astrology"}), 422, "INVALID_CATEGORY")
    error(api.put(f"{URL}/AUTH-001", json={"conditions": {"threshold": 0}}), 422, "INVALID_CONDITION")
    error(api.put(f"{URL}/AUTH-001", json={}), 422, "INVALID_RULE")
    error(api.put(f"{URL}/AUTH-001", json={"rule_id": "AUTH-999"}), 422, "INVALID_RULE")
    error(api.put(f"{URL}/AUTH-001", json={"updated_at": "2001-01-01T00:00:00Z"}), 422, "INVALID_RULE")
    error(api.put(f"{URL}/NOPE-001", json={"name": "x"}), 404, "RULE_NOT_FOUND")
    assert api.get(f"{URL}/AUTH-001").json()["rule"]["severity"] == "high"


# -- status ---------------------------------------------------------------------------------

def test_enable_disable(api):
    response = api.patch(f"{URL}/AUTH-001/status", json={"enabled": False})
    assert response.json() == {"success": True, "rule_id": "AUTH-001", "enabled": False}
    assert api.get(f"{URL}/AUTH-001").json()["rule"]["enabled"] is False
    assert api.patch(f"{URL}/AUTH-001/status", json={"enabled": True}).json()["enabled"] is True


def test_status_invalid_and_missing(api):
    error(api.patch(f"{URL}/AUTH-001/status", json={"enabled": "false"}), 422, "INVALID_STATUS")
    error(api.patch(f"{URL}/AUTH-001/status", json={}), 422, "INVALID_STATUS")
    error(api.patch(f"{URL}/NOPE-001/status", json={"enabled": True}), 404, "RULE_NOT_FOUND")


# -- delete ---------------------------------------------------------------------------------

def test_delete_rule(api):
    api.post(URL, json=rule_payload())
    response = api.delete(f"{URL}/AUTH-004")
    assert response.status_code == 200 and response.json()["success"] is True
    error(api.get(f"{URL}/AUTH-004"), 404, "RULE_NOT_FOUND")


def test_delete_missing(api):
    error(api.delete(f"{URL}/NOPE-001"), 404, "RULE_NOT_FOUND")


def test_initial_rules_are_protected_from_accidental_delete(api):
    error(api.delete(f"{URL}/AUTH-001"), 409, "RULE_PROTECTED")
    assert api.get(f"{URL}/AUTH-001").status_code == 200
    assert api.delete(f"{URL}/AUTH-001?force=true").status_code == 200
    error(api.get(f"{URL}/AUTH-001"), 404, "RULE_NOT_FOUND")


# -- detection integration ------------------------------------------------------------------

@pytest.fixture
def failed_logins(mongo_db):
    from app.repositories.event_repository import EventRepository

    events = [make(seconds=i * 10, source_ip="10.9.9.9") for i in range(6)]
    EventRepository(mongo_db).create_many(events)
    return events


def matches(client, event_id):
    body = client.post(f"/api/v1/detection/evaluate/{event_id}").json()
    return {m["rule_id"] for m in body["matches"]}


def test_disabling_and_enabling_a_rule_changes_detection(api, failed_logins):
    event_id = failed_logins[-1].event_id
    assert "AUTH-001" in matches(api, event_id)

    api.patch(f"{URL}/AUTH-001/status", json={"enabled": False})
    assert "AUTH-001" not in matches(api, event_id)

    api.patch(f"{URL}/AUTH-001/status", json={"enabled": True})
    assert "AUTH-001" in matches(api, event_id)


def test_updated_threshold_takes_effect_immediately(api, failed_logins):
    event_id = failed_logins[-1].event_id
    api.put(f"{URL}/AUTH-001", json={"conditions": {"event_type": "authentication", "status": "failed", "threshold": 7, "window_minutes": 5}})
    assert "AUTH-001" not in matches(api, event_id)  # only 6 failures now
    api.put(f"{URL}/AUTH-001", json={"conditions": {"event_type": "authentication", "status": "failed", "threshold": 6, "window_minutes": 5}})
    assert "AUTH-001" in matches(api, event_id)


def test_new_rule_and_deleted_rule_affect_detection(api, failed_logins):
    event_id = failed_logins[-1].event_id
    api.post(URL, json=rule_payload(rule_id="AUTH-777", conditions={"event_type": "authentication", "status": "failed", "threshold": 3, "window_minutes": 5}))
    assert "AUTH-777" in matches(api, event_id)
    api.delete(f"{URL}/AUTH-777")
    assert "AUTH-777" not in matches(api, event_id)


def test_existing_endpoints_still_work(api):
    assert api.get("/api/v1/health").status_code == 200
    assert api.get("/api/v1/events").status_code == 200
