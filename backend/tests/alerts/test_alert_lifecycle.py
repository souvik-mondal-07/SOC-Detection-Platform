"""Step 12: alert lifecycle (status transitions, acknowledgement, history, stats). Uses real alerts in mongomock."""

from itertools import count

import pytest

from app.core.errors import DatabaseUnavailableError
from app.models.alert import ALLOWED_TRANSITIONS, Alert, AlertStatus
from app.services.alert_service import AlertService, StatusConflictError

BASE = "/api/v1/alerts"
_n = count(1)


def make_alert(**overrides) -> Alert:
    n = next(_n)
    data = dict(
        alert_id=f"ALT-20261105-{n:06d}", rule_id="AUTH-001", title="Multiple Failed Logins Detected",
        description="Five failed logins in one minute", severity="high", priority_score=83, priority_reason="High severity",
        source_ip="192.168.1.20", event_ids=[f"evt_{n:05d}", f"evt_{n + 500:05d}"],
    )
    return Alert(**{**data, **overrides})


@pytest.fixture
def alert(alert_repo):
    return alert_repo.create_alert(make_alert())


def patch(client, target_id, status, reason=None, **extra):
    body = {"status": status, **({"reason": reason} if reason is not None else {}), **extra}
    return client.patch(f"{BASE}/{target_id}/status", json=body)


def get(client, alert_id):
    return client.get(f"{BASE}/{alert_id}").json()["alert"]


# -- acknowledge -------------------------------------------------------------------------------------


def test_acknowledge_keeps_status_open_and_records_history(client, alert):
    r = client.post(f"{BASE}/{alert.alert_id}/acknowledge")
    assert r.status_code == 200
    body = r.json()["alert"]
    assert body["status"] == "open" and body["acknowledged_at"] is not None
    assert [(h["action"], h["previous_status"], h["new_status"], h["reason"]) for h in body["status_history"]] == [("acknowledged", "open", "open", None)]
    assert body["updated_at"] >= body["created_at"]
    # still shows up in the existing open filter, and in the list item
    listing = client.get(f"{BASE}?status=open").json()
    assert listing["total"] == 1 and listing["alerts"][0]["acknowledged_at"] is not None


def test_acknowledge_twice_is_rejected_and_adds_no_history(client, alert):
    assert client.post(f"{BASE}/{alert.alert_id}/acknowledge").status_code == 200
    r = client.post(f"{BASE}/{alert.alert_id}/acknowledge")
    assert r.status_code == 409 and r.json() == {"error": {"message": "The alert is already acknowledged"}}
    assert len(get(client, alert.alert_id)["status_history"]) == 1


def test_only_open_alerts_can_be_acknowledged(client, alert):
    patch(client, alert.alert_id, "investigating")
    r = client.post(f"{BASE}/{alert.alert_id}/acknowledge")
    assert r.status_code == 409 and "Only open alerts" in r.json()["error"]["message"]


def test_acknowledge_missing_alert_404(client, db):
    r = client.post(f"{BASE}/ALT-20261105-999999/acknowledge")
    assert r.status_code == 404 and r.json() == {"error": {"message": "Alert not found"}}


# -- transitions ---------------------------------------------------------------------------------------


def test_move_to_investigating_without_reason(client, alert):
    r = patch(client, alert.alert_id, "investigating")
    body = r.json()["alert"]
    assert r.status_code == 200 and r.json()["success"] and body["status"] == "investigating"
    assert body["status_history"][0]["previous_status"] == "open" and body["status_history"][0]["reason"] is None
    assert body["updated_at"] >= body["created_at"]


def test_resolve_requires_note_and_stores_it(client, alert):
    for blank in (None, "", "   "):
        r = patch(client, alert.alert_id, "resolved", blank)
        assert r.status_code == 422 and "resolution note" in r.json()["error"]["message"], blank
    assert get(client, alert.alert_id)["status"] == "open"  # nothing changed
    r = patch(client, alert.alert_id, "resolved", "  Password reset, user confirmed.  ")
    body = r.json()["alert"]
    assert r.status_code == 200 and body["status"] == "resolved" and body["resolution_note"] == "Password reset, user confirmed."
    assert body["status_history"][-1]["reason"] == "Password reset, user confirmed."


def test_false_positive_requires_reason(client, alert):
    r = patch(client, alert.alert_id, "false_positive")
    assert r.status_code == 422 and "false-positive reason" in r.json()["error"]["message"]
    r = patch(client, alert.alert_id, "false_positive", "Vulnerability scanner at 192.168.1.20")
    assert r.status_code == 200 and r.json()["alert"]["resolution_note"] == "Vulnerability scanner at 192.168.1.20"


def test_investigating_can_be_resolved_or_returned_to_open(client, alert):
    patch(client, alert.alert_id, "investigating")
    assert patch(client, alert.alert_id, "open").json()["alert"]["status"] == "open"
    patch(client, alert.alert_id, "investigating")
    assert patch(client, alert.alert_id, "resolved", "done").json()["alert"]["status"] == "resolved"


@pytest.mark.parametrize("closed", ["resolved", "false_positive"])
def test_reopen_closed_alert_needs_reason_and_clears_note(client, alert, closed):
    client.post(f"{BASE}/{alert.alert_id}/acknowledge")
    assert patch(client, alert.alert_id, closed, "closing note").status_code == 200
    r = patch(client, alert.alert_id, "open")
    assert r.status_code == 422 and "reopen" in r.json()["error"]["message"]
    r = patch(client, alert.alert_id, "open", "New activity from the same IP")
    body = r.json()["alert"]
    assert r.status_code == 200 and body["status"] == "open"
    assert body["resolution_note"] is None and body["acknowledged_at"] is None  # back in the triage queue
    assert [h["new_status"] for h in body["status_history"]] == ["open", closed, "open"]  # history keeps the old note
    assert body["status_history"][1]["reason"] == "closing note"


@pytest.mark.parametrize(
    ("setup", "target"),
    [(["resolved"], "investigating"), (["resolved"], "false_positive"), (["false_positive"], "resolved"), (["false_positive"], "investigating")],
)
def test_disallowed_transitions_are_rejected(client, alert, setup, target):
    for step in setup:
        assert patch(client, alert.alert_id, step, "note").status_code == 200
    before = get(client, alert.alert_id)
    r = patch(client, alert.alert_id, target, "note")
    assert r.status_code == 409 and "cannot be changed" in r.json()["error"]["message"]
    assert get(client, alert.alert_id) == before  # unchanged, no history entry


def test_requesting_the_current_status_is_rejected(client, alert):
    r = patch(client, alert.alert_id, "open", "x")
    assert r.status_code == 409 and r.json()["error"]["message"] == "The alert is already open"
    patch(client, alert.alert_id, "resolved", "ok")
    r = patch(client, alert.alert_id, "resolved", "again")  # a repeated request must not duplicate history
    assert r.status_code == 409
    assert len(get(client, alert.alert_id)["status_history"]) == 1


def test_transition_table_covers_every_status():
    assert set(ALLOWED_TRANSITIONS) == {s.value for s in AlertStatus}
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert source not in targets


# -- validation -----------------------------------------------------------------------------------------


def test_invalid_status_value_and_missing_status_422(client, alert):
    assert patch(client, alert.alert_id, "closed", "x").status_code == 422
    assert patch(client, alert.alert_id, "").status_code == 422
    assert client.patch(f"{BASE}/{alert.alert_id}/status", json={"reason": "x"}).status_code == 422
    assert client.patch(f"{BASE}/{alert.alert_id}/status", json={"status": None}).status_code == 422


@pytest.mark.parametrize("field", ["severity", "priority_score", "alert_id", "event_ids", "rule_id", "updated_at", "status_history", "acknowledged_at", "$set"])
def test_unsupported_fields_are_rejected(client, alert, field):
    r = patch(client, alert.alert_id, "investigating", **{field: "critical"})
    assert r.status_code == 422
    assert get(client, alert.alert_id)["status"] == "open"


def test_reason_length_limit(client, alert):
    assert patch(client, alert.alert_id, "resolved", "x" * 1001).status_code == 422
    assert patch(client, alert.alert_id, "resolved", "x" * 1000).status_code == 200


def test_missing_alert_404_and_bad_id_422(client, db):
    r = patch(client, "ALT-20261105-999999", "investigating")
    assert r.status_code == 404 and r.json() == {"error": {"message": "Alert not found"}}
    assert patch(client, "bad id!", "investigating").status_code == 422


# -- integrity ------------------------------------------------------------------------------------------


def test_lifecycle_never_changes_detection_data(client, alert_repo, alert):
    patch(client, alert.alert_id, "investigating")
    patch(client, alert.alert_id, "false_positive", "benign")
    patch(client, alert.alert_id, "open", "recheck")
    after = alert_repo.get_alert_by_id(alert.alert_id)
    for name in ("alert_id", "rule_id", "title", "description", "severity", "priority_score", "priority_reason", "source_ip", "event_ids", "created_at"):
        assert getattr(after, name) == getattr(alert, name), name
    assert after.updated_at >= alert.updated_at


def test_status_change_does_not_create_alerts(client, alert_repo, alert):
    patch(client, alert.alert_id, "resolved", "done")
    assert client.get(BASE).json()["total"] == 1


def test_history_is_saved_and_retrieved_in_order(client, alert):
    patch(client, alert.alert_id, "investigating")
    patch(client, alert.alert_id, "resolved", "fixed")
    patch(client, alert.alert_id, "open", "came back")
    history = get(client, alert.alert_id)["status_history"]
    assert [(h["previous_status"], h["new_status"]) for h in history] == [("open", "investigating"), ("investigating", "resolved"), ("resolved", "open")]
    assert all(h["timestamp"] and set(h) == {"action", "previous_status", "new_status", "timestamp", "reason"} for h in history)  # no actor
    assert [h["timestamp"] for h in history] == sorted(h["timestamp"] for h in history)


def test_alerts_stored_before_step_12_still_work(client, db, alert_repo):
    legacy = make_alert().to_document()
    for key in ("acknowledged_at", "resolution_note", "status_history"):
        del legacy[key]
    db["alerts"].insert_one(legacy)
    body = get(client, legacy["alert_id"])
    assert body["status_history"] == [] and body["acknowledged_at"] is None and body["resolution_note"] is None
    assert client.post(f"{BASE}/{legacy['alert_id']}/acknowledge").status_code == 200
    assert patch(client, legacy["alert_id"], "resolved", "ok").json()["alert"]["status"] == "resolved"
    assert [h["action"] for h in get(client, legacy["alert_id"])["status_history"]] == ["acknowledged", "status_change"]


def test_alert_without_stored_status_is_treated_as_open(client, db):
    doc = make_alert().to_document()
    del doc["status"]
    db["alerts"].insert_one(doc)
    assert patch(client, doc["alert_id"], "investigating").status_code == 200


# -- concurrency -----------------------------------------------------------------------------------------


def test_stale_read_cannot_overwrite_a_concurrent_change(alert_repo, rule_repo, event_repo, alert, monkeypatch):
    service = AlertService(alert_repo, rule_repo, event_repo)
    stale = alert_repo.get_alert_by_id(alert.alert_id)  # both requests read "open"
    assert service.change_status(alert.alert_id, "false_positive", "benign").status == "false_positive"  # request A wins
    monkeypatch.setattr(alert_repo, "get_alert_by_id", lambda _id: stale)  # request B still sees the old state
    with pytest.raises(StatusConflictError):
        service.change_status(alert.alert_id, "resolved", "B")
    monkeypatch.undo()
    current = alert_repo.get_alert_by_id(alert.alert_id)
    assert current.status == "false_positive" and current.resolution_note == "benign" and len(current.status_history) == 1


def test_concurrent_conflict_is_http_409(client, alert_repo, alert, monkeypatch):
    stale = alert_repo.get_alert_by_id(alert.alert_id)
    patch(client, alert.alert_id, "resolved", "A")
    from app.repositories.alert_repository import AlertRepository

    real = AlertRepository.get_alert_by_id
    calls = {"n": 0}

    def first_call_stale(self, alert_id):
        calls["n"] += 1
        return stale if calls["n"] == 1 else real(self, alert_id)

    monkeypatch.setattr(AlertRepository, "get_alert_by_id", first_call_stale)
    r = patch(client, alert.alert_id, "investigating")
    assert r.status_code == 409 and "changed by someone else" in r.json()["error"]["message"]


def test_history_keeps_only_the_newest_200_entries(alert_repo, alert):
    for i in range(205):
        entry = {"action": "status_change", "previous_status": "open", "new_status": "open", "timestamp": alert.created_at, "reason": f"r{i}"}
        assert alert_repo.apply_transition(alert.alert_id, expected_status="open", changes={"updated_at": alert.updated_at}, history_entry=entry)
    history = alert_repo.get_alert_by_id(alert.alert_id).status_history
    assert len(history) == 200 and history[0].reason == "r5" and history[-1].reason == "r204"


# -- de-duplication and investigations -------------------------------------------------------------------


def test_acknowledged_alert_still_deduplicates_new_detection(client, db, burst):
    first = client.post(f"{BASE}/generate/{burst[-1].event_id}").json()["alerts"][0]["alert_id"]
    client.post(f"{BASE}/{first}/acknowledge")
    again = client.post(f"{BASE}/generate/{burst[-1].event_id}").json()
    assert again["alerts_created"] == 0 and again["duplicates_skipped"] == 1


def test_alert_and_investigation_status_are_independent(client, db, alert):
    inv = client.post("/api/v1/investigations", json={"title": "Case", "alert_ids": [alert.alert_id]}).json()["investigation"]
    url = f"/api/v1/investigations/{inv['investigation_id']}"
    patch(client, alert.alert_id, "resolved", "done")
    after = client.get(url).json()["investigation"]
    assert after["status"] == "open" and after["alerts"][0]["status"] == "resolved"  # investigation untouched, alert shown live
    client.patch(url, json={"status": "closed"})
    assert get(client, alert.alert_id)["status"] == "resolved"
    patch(client, alert.alert_id, "open", "reopen")
    client.patch(url, json={"status": "in_progress"})
    assert get(client, alert.alert_id)["status"] == "open"  # closing/reopening the case never moves the alert
    linked = client.get(f"/api/v1/investigations?alert_id={alert.alert_id}").json()
    assert linked["total"] == 1  # alert -> investigation link is preserved


# -- stats ---------------------------------------------------------------------------------------------------


def test_stats_empty(client, db):
    body = client.get(f"{BASE}/stats").json()
    assert body == {
        "success": True, "total": 0, "by_status": {"open": 0, "investigating": 0, "resolved": 0, "false_positive": 0},
        "by_severity": {"low": 0, "medium": 0, "high": 0, "critical": 0}, "active": 0, "high_critical_active": 0, "acknowledged_open": 0,
    }


def test_stats_are_exact_counts_across_all_alerts(client, alert_repo):
    spec = [("critical", "open"), ("critical", "resolved"), ("high", "investigating"), ("high", "false_positive"), ("medium", "open"), ("low", "open")]
    alerts = [alert_repo.create_alert(make_alert(severity=sev, priority_score=50)) for sev, _ in spec]
    for a, (_, status) in zip(alerts, spec):
        if status == "investigating":
            patch(client, a.alert_id, "investigating")
        elif status != "open":
            patch(client, a.alert_id, status, "note")
    client.post(f"{BASE}/{alerts[0].alert_id}/acknowledge")
    body = client.get(f"{BASE}/stats").json()
    assert body["total"] == 6
    assert body["by_status"] == {"open": 3, "investigating": 1, "resolved": 1, "false_positive": 1}
    assert body["by_severity"] == {"low": 1, "medium": 1, "high": 2, "critical": 2}
    assert body["active"] == 4
    assert body["high_critical_active"] == 2  # critical/open + high/investigating; resolved and false-positive excluded
    assert body["acknowledged_open"] == 1
    # the same totals the existing list endpoint reports
    assert client.get(f"{BASE}?status=open").json()["total"] == body["by_status"]["open"]


def test_stats_route_is_not_shadowed_by_alert_id(client, db):
    assert client.get(f"{BASE}/stats").status_code == 200


def test_database_failure_503_on_status_update(client, db, alert, monkeypatch):
    from app.repositories.alert_repository import AlertRepository

    def boom(*_a, **_k):
        raise DatabaseUnavailableError("mongodb://user:pw@host")

    monkeypatch.setattr(AlertRepository, "apply_transition", boom)
    r = patch(client, alert.alert_id, "investigating")
    assert r.status_code == 503 and "mongodb" not in r.text
