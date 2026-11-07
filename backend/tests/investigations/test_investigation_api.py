import pytest

from app.core.errors import DatabaseUnavailableError
from app.models.investigation import ALLOWED_TRANSITIONS, InvestigationStatus

BASE = "/api/v1/investigations"


def create(client, alert_ids, title="Suspicious logins"):
    return client.post(BASE, json={"title": title, "alert_ids": alert_ids})


# -- create ---------------------------------------------------------------------------------------


def test_create_returns_detail_with_alert_context(client, db, alerts):
    r = create(client, [alerts[0].alert_id, alerts[1].alert_id])
    assert r.status_code == 201
    inv = r.json()["investigation"]
    assert r.json()["success"] is True
    assert inv["investigation_id"].startswith("INV-") and inv["status"] == "open"
    assert inv["alert_count"] == 2 and inv["note_count"] == 0 and inv["notes"] == []
    assert inv["created_at"] and inv["updated_at"]
    first = inv["alerts"][0]
    assert first == {
        "alert_id": alerts[0].alert_id, "available": True, "rule_id": "AUTH-001", "title": "Multiple Failed Logins Detected",
        "severity": "critical", "priority_score": 95, "status": "open", "source_ip": "10.0.0.9",
        "created_at": first["created_at"], "event_count": 2, "event_ids": list(alerts[0].event_ids),
    }
    assert inv["alerts"][1]["source_ip"] is None
    assert "_id" not in inv


def test_ids_are_unique_and_sequential(client, db, alerts):
    ids = [create(client, [alerts[0].alert_id]).json()["investigation"]["investigation_id"] for _ in range(3)]
    assert len(set(ids)) == 3 and ids == sorted(ids)


def test_create_rejects_unknown_alert_without_creating_anything(client, db, alerts):
    r = create(client, [alerts[0].alert_id, "ALT-20261014-999999"])
    assert r.status_code == 404 and "ALT-20261014-999999" in r.json()["error"]["message"]
    assert client.get(BASE).json()["total"] == 0
    assert db["alerts"].count_documents({}) == 3  # nonexistent alert was not silently created


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": "x"},
        {"alert_ids": ["ALT-1"]},
        {"title": "", "alert_ids": ["ALT-1"]},
        {"title": "   ", "alert_ids": ["ALT-1"]},
        {"title": "x" * 201, "alert_ids": ["ALT-1"]},
        {"title": "x", "alert_ids": []},
        {"title": "x", "alert_ids": ["ALT-1", "ALT-1"]},
        {"title": "x", "alert_ids": ["bad id!"]},
        {"title": "x", "alert_ids": [{"$ne": None}]},
        {"title": "x", "alert_ids": ["ALT-" + str(i) for i in range(101)]},
        {"title": "x", "alert_ids": ["ALT-1"], "status": "closed"},
        {"title": "x", "alert_ids": ["ALT-1"], "investigation_id": "INV-1"},
        {"title": "x", "alert_ids": ["ALT-1"], "notes": []},
    ],
)
def test_create_validation(client, db, body):
    r = client.post(BASE, json=body)
    assert r.status_code == 422 and r.json()["error"]["message"] == "Validation failed"


# -- list / get -----------------------------------------------------------------------------------


def test_list_empty(client, db):
    assert client.get(BASE).json() == {"success": True, "page": 1, "limit": 20, "total": 0, "count": 0, "investigations": []}


def test_list_newest_first_with_summary_fields(client, db, alerts):
    first = create(client, [alerts[0].alert_id], "first").json()["investigation"]["investigation_id"]
    second = create(client, [alerts[0].alert_id, alerts[1].alert_id], "second").json()["investigation"]["investigation_id"]
    body = client.get(BASE).json()
    assert [i["investigation_id"] for i in body["investigations"]] == [second, first]
    item = body["investigations"][0]
    assert item["alert_count"] == 2 and item["note_count"] == 0 and item["title"] == "second"
    assert "alerts" not in item and "notes" not in item and "_id" not in item


def test_list_filters_and_pagination(client, db, alerts):
    a, b, c = (create(client, [alerts[i].alert_id], t).json()["investigation"]["investigation_id"] for i, t in ((0, "Alpha scan"), (1, "Beta login"), (2, "alpha again")))
    client.patch(f"{BASE}/{b}", json={"status": "in_progress"})
    client.patch(f"{BASE}/{c}", json={"status": "closed"})

    assert client.get(f"{BASE}?status=open").json()["total"] == 1
    assert client.get(f"{BASE}?status=in_progress").json()["investigations"][0]["investigation_id"] == b
    assert client.get(f"{BASE}?status=closed").json()["investigations"][0]["investigation_id"] == c
    assert client.get(f"{BASE}?alert_id={alerts[1].alert_id}").json()["total"] == 1
    assert client.get(f"{BASE}?alert_id=ALT-nothing").json()["total"] == 0
    assert {i["title"] for i in client.get(f"{BASE}?title=ALPHA").json()["investigations"]} == {"Alpha scan", "alpha again"}
    assert client.get(f"{BASE}?title=.*").json()["total"] == 0  # regex characters are literal text

    page1 = client.get(f"{BASE}?limit=2&page=1").json()
    page2 = client.get(f"{BASE}?limit=2&page=2").json()
    assert (page1["total"], page1["count"], page2["count"]) == (3, 2, 1)
    assert [i["investigation_id"] for i in page1["investigations"] + page2["investigations"]] == [c, b, a]
    assert client.get(f"{BASE}?page=9").json()["investigations"] == []


@pytest.mark.parametrize("query", ["limit=101", "limit=0", "page=0", "status=completed", "status=bogus", "alert_id=bad%20id", "title=", "title=" + "x" * 101])
def test_list_validation(client, db, query):
    assert client.get(f"{BASE}?{query}").status_code == 422, query


def test_get_investigation(client, db, investigation):
    r = client.get(f"{BASE}/{investigation['investigation_id']}")
    assert r.status_code == 200 and r.json()["investigation"] == investigation


def test_get_missing_and_invalid_ids(client, db):
    missing = client.get(f"{BASE}/INV-20261014-000099")
    assert missing.status_code == 404 and missing.json() == {"error": {"message": "Investigation not found"}}
    assert client.get(f"{BASE}/bad id!").status_code == 422
    assert client.get(f"{BASE}/{'x' * 65}").status_code == 422
    assert client.patch(f"{BASE}/INV-20261014-000099", json={"title": "x"}).status_code == 404
    assert client.post(f"{BASE}/INV-20261014-000099/notes", json={"text": "x"}).status_code == 404
    assert client.post(f"{BASE}/INV-20261014-000099/alerts", json={"alert_ids": ["a"]}).status_code == 404
    assert client.delete(f"{BASE}/INV-20261014-000099/alerts/a").status_code == 404


# -- status ---------------------------------------------------------------------------------------


def test_status_lifecycle(client, db, investigation):
    url = f"{BASE}/{investigation['investigation_id']}"
    for status in ("in_progress", "closed", "in_progress", "open", "closed"):
        r = client.patch(url, json={"status": status})
        assert r.status_code == 200 and r.json()["investigation"]["status"] == status
    assert client.get(url).json()["investigation"]["status"] == "closed"


def test_every_transition_is_enforced(client, db, alerts):
    for current in InvestigationStatus:
        for target in InvestigationStatus:
            if current == target:
                continue
            inv_id = create(client, [alerts[0].alert_id]).json()["investigation"]["investigation_id"]
            # walk to `current` through allowed steps
            path = {"open": [], "in_progress": ["in_progress"], "closed": ["closed"]}[current.value]
            for step in path:
                assert client.patch(f"{BASE}/{inv_id}", json={"status": step}).status_code == 200
            r = client.patch(f"{BASE}/{inv_id}", json={"status": target.value})
            expected = 200 if target.value in ALLOWED_TRANSITIONS[current.value] else 409
            assert r.status_code == expected, (current, target)
            if expected == 409:
                assert "Cannot change status" in r.json()["error"]["message"]


def test_closed_cannot_go_straight_back_to_open(client, db, investigation):
    url = f"{BASE}/{investigation['investigation_id']}"
    client.patch(url, json={"status": "closed"})
    assert client.patch(url, json={"status": "open"}).status_code == 409
    assert client.get(url).json()["investigation"]["status"] == "closed"


def test_same_status_is_a_noop(client, db, investigation):
    url = f"{BASE}/{investigation['investigation_id']}"
    r = client.patch(url, json={"status": "open"})
    assert r.status_code == 200 and r.json()["investigation"]["updated_at"] == investigation["updated_at"]


@pytest.mark.parametrize("body", [{"status": "completed"}, {"status": "CLOSED"}, {"status": ""}, {"status": None}, {"status": 1}, {"title": None}, {"title": ""}, {"title": "  "}, {}, {"alert_ids": ["a"]}, {"severity": "low"}, {"notes": []}])
def test_update_validation(client, db, investigation, body):
    assert client.patch(f"{BASE}/{investigation['investigation_id']}", json=body).status_code == 422
    assert client.get(f"{BASE}/{investigation['investigation_id']}").json()["investigation"]["status"] == "open"


def test_patch_title_updates_timestamp_but_not_created_at(client, db, investigation):
    r = client.patch(f"{BASE}/{investigation['investigation_id']}", json={"title": "  Renamed  "}).json()["investigation"]
    assert r["title"] == "Renamed" and r["created_at"] == investigation["created_at"] and r["updated_at"] >= investigation["updated_at"]


def test_status_change_does_not_touch_alerts(client, db, alerts, investigation):
    before = db["alerts"].find_one({"alert_id": alerts[0].alert_id}, {"_id": 0})
    url = f"{BASE}/{investigation['investigation_id']}"
    client.patch(url, json={"status": "in_progress"})
    client.patch(url, json={"status": "closed"})
    after = db["alerts"].find_one({"alert_id": alerts[0].alert_id}, {"_id": 0})
    assert before == after and after["status"] == "open"


# -- linking --------------------------------------------------------------------------------------


def test_link_alerts(client, db, alerts, investigation):
    url = f"{BASE}/{investigation['investigation_id']}/alerts"
    r = client.post(url, json={"alert_ids": [alerts[1].alert_id, alerts[2].alert_id]})
    assert r.status_code == 200
    inv = r.json()["investigation"]
    assert inv["alert_ids"] == [a.alert_id for a in alerts] and inv["alert_count"] == 3
    assert [a["severity"] for a in inv["alerts"]] == ["critical", "medium", "low"]
    assert inv["updated_at"] >= investigation["updated_at"]


def test_link_rejects_unknown_alert_and_links_nothing(client, db, alerts, investigation):
    url = f"{BASE}/{investigation['investigation_id']}/alerts"
    r = client.post(url, json={"alert_ids": [alerts[1].alert_id, "ALT-ghost"]})
    assert r.status_code == 404 and "ALT-ghost" in r.json()["error"]["message"]
    assert client.get(f"{BASE}/{investigation['investigation_id']}").json()["investigation"]["alert_count"] == 1


def test_link_rejects_duplicates(client, db, alerts, investigation):
    url = f"{BASE}/{investigation['investigation_id']}/alerts"
    r = client.post(url, json={"alert_ids": [alerts[0].alert_id]})
    assert r.status_code == 409 and "already linked" in r.json()["error"]["message"]
    r = client.post(url, json={"alert_ids": [alerts[1].alert_id, alerts[0].alert_id]})  # mixed: nothing is linked
    assert r.status_code == 409
    assert client.get(f"{BASE}/{investigation['investigation_id']}").json()["investigation"]["alert_count"] == 1
    assert client.post(url, json={"alert_ids": [alerts[1].alert_id, alerts[1].alert_id]}).status_code == 422


@pytest.mark.parametrize("body", [{}, {"alert_ids": []}, {"alert_ids": "ALT-1"}, {"alert_ids": ["bad id"]}, {"alert_ids": [{"$gt": ""}]}, {"alert_ids": ["a"], "extra": 1}])
def test_link_validation(client, db, investigation, body):
    assert client.post(f"{BASE}/{investigation['investigation_id']}/alerts", json=body).status_code == 422


def test_linking_leaves_alert_documents_unchanged(client, db, alerts, investigation):
    before = list(db["alerts"].find({}, {"_id": 0}).sort("alert_id"))
    client.post(f"{BASE}/{investigation['investigation_id']}/alerts", json={"alert_ids": [alerts[1].alert_id]})
    assert list(db["alerts"].find({}, {"_id": 0}).sort("alert_id")) == before


def test_one_alert_can_be_in_several_investigations(client, db, alerts, investigation):
    other = create(client, [alerts[0].alert_id], "second look").json()["investigation"]
    assert other["investigation_id"] != investigation["investigation_id"]
    assert client.get(f"{BASE}?alert_id={alerts[0].alert_id}").json()["total"] == 2


# -- unlinking ------------------------------------------------------------------------------------


def test_unlink_alert(client, db, alerts, investigation):
    inv_id = investigation["investigation_id"]
    client.post(f"{BASE}/{inv_id}/alerts", json={"alert_ids": [alerts[1].alert_id]})
    r = client.delete(f"{BASE}/{inv_id}/alerts/{alerts[0].alert_id}")
    assert r.status_code == 200 and r.json()["investigation"]["alert_ids"] == [alerts[1].alert_id]
    assert db["alerts"].count_documents({"alert_id": alerts[0].alert_id}) == 1  # the alert itself still exists
    assert client.get(f"{BASE}?alert_id={alerts[0].alert_id}").json()["total"] == 0


def test_unlink_errors(client, db, alerts, investigation):
    inv_id = investigation["investigation_id"]
    not_linked = client.delete(f"{BASE}/{inv_id}/alerts/{alerts[1].alert_id}")
    assert not_linked.status_code == 404 and "not linked" in not_linked.json()["error"]["message"]
    last = client.delete(f"{BASE}/{inv_id}/alerts/{alerts[0].alert_id}")
    assert last.status_code == 409 and "at least one" in last.json()["error"]["message"]
    assert client.get(f"{BASE}/{inv_id}").json()["investigation"]["alert_count"] == 1
    assert client.delete(f"{BASE}/{inv_id}/alerts/bad%20id").status_code == 422


def test_deleted_alert_is_shown_as_unavailable(client, db, alerts, investigation):
    inv_id = investigation["investigation_id"]
    client.post(f"{BASE}/{inv_id}/alerts", json={"alert_ids": [alerts[1].alert_id]})
    db["alerts"].delete_one({"alert_id": alerts[0].alert_id})  # no API deletes alerts today; simulate it
    inv = client.get(f"{BASE}/{inv_id}").json()["investigation"]
    assert inv["unavailable_alert_count"] == 1
    assert inv["alerts"][0] == {
        "alert_id": alerts[0].alert_id, "available": False, "rule_id": None, "title": None, "severity": None,
        "priority_score": None, "status": None, "source_ip": None, "created_at": None, "event_count": 0, "event_ids": [],
    }
    assert inv["alerts"][1]["available"] is True
    assert client.delete(f"{BASE}/{inv_id}/alerts/{alerts[0].alert_id}").status_code == 200  # can still be unlinked


def test_event_ids_in_context_are_capped(client, db, alert_repo):
    from tests.investigations.conftest import build_alert

    big = alert_repo.create_alert(build_alert(event_ids=[f"evt_{i}" for i in range(120)]))
    alert = create(client, [big.alert_id]).json()["investigation"]["alerts"][0]
    assert alert["event_count"] == 120 and len(alert["event_ids"]) == 50


# -- notes ----------------------------------------------------------------------------------------


def test_add_notes_keeps_history_in_order(client, db, investigation):
    url = f"{BASE}/{investigation['investigation_id']}/notes"
    first = client.post(url, json={"text": "  Checked auth logs.  "})
    assert first.status_code == 201
    second = client.post(url, json={"text": "Source IP is on the allow-list."})
    inv = second.json()["investigation"]
    assert [n["text"] for n in inv["notes"]] == ["Checked auth logs.", "Source IP is on the allow-list."]
    assert inv["note_count"] == 2
    ids = [n["note_id"] for n in inv["notes"]]
    assert len(set(ids)) == 2 and all(i.startswith("note_") for i in ids)
    assert all(set(n) == {"note_id", "text", "created_at"} for n in inv["notes"])  # no invented author
    assert client.get(f"{BASE}/{investigation['investigation_id']}").json()["investigation"]["notes"] == inv["notes"]
    assert inv["updated_at"] >= investigation["updated_at"]


@pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "   \n\t "}, {"text": None}, {"text": 5}, {"text": ["a"]}, {"text": "x" * 2001}, {"text": "ok", "author": "alice"}, {"text": "ok", "note_id": "n1"}])
def test_note_validation(client, db, investigation, body):
    r = client.post(f"{BASE}/{investigation['investigation_id']}/notes", json=body)
    assert r.status_code == 422
    assert client.get(f"{BASE}/{investigation['investigation_id']}").json()["investigation"]["notes"] == []


def test_note_at_max_length_is_accepted(client, db, investigation):
    assert client.post(f"{BASE}/{investigation['investigation_id']}/notes", json={"text": "x" * 2000}).status_code == 201


def test_note_count_limit(client, db, investigation):
    inv_id = investigation["investigation_id"]
    from app.models.investigation import MAX_NOTES_PER_INVESTIGATION

    now = db["investigations"].find_one({"investigation_id": inv_id})["created_at"]
    db["investigations"].update_one(
        {"investigation_id": inv_id},
        {"$set": {"notes": [{"note_id": f"note_{i}", "text": "t", "created_at": now} for i in range(MAX_NOTES_PER_INVESTIGATION)]}},
    )
    r = client.post(f"{BASE}/{inv_id}/notes", json={"text": "one too many"})
    assert r.status_code == 409 and "at most" in r.json()["error"]["message"]


def test_note_script_text_is_stored_as_plain_text(client, db, investigation):
    payload = "<script>alert(1)</script> {\"$ne\": 1}"
    inv = client.post(f"{BASE}/{investigation['investigation_id']}/notes", json={"text": payload}).json()["investigation"]
    assert inv["notes"][0]["text"] == payload  # stored verbatim; the frontend renders text, never HTML


# -- database failures / errors -------------------------------------------------------------------


@pytest.mark.parametrize("method,path,body", [
    ("get", "", None),
    ("get", "/INV-1", None),
    ("post", "", {"title": "t", "alert_ids": ["a"]}),
    ("patch", "/INV-1", {"title": "t"}),
    ("post", "/INV-1/alerts", {"alert_ids": ["a"]}),
    ("delete", "/INV-1/alerts/a", None),
    ("post", "/INV-1/notes", {"text": "t"}),
])
def test_database_unavailable_returns_503_without_details(client, db, monkeypatch, method, path, body):
    from app.repositories.base import BaseRepository

    def boom(*_a, **_k):
        raise DatabaseUnavailableError("mongodb://user:secret@host unreachable")

    monkeypatch.setattr(BaseRepository, "find_by_id", boom)
    monkeypatch.setattr("app.repositories.investigation_repository.InvestigationRepository.get_investigations", boom)
    monkeypatch.setattr("app.repositories.alert_repository.AlertRepository.get_alerts_by_ids", boom)
    r = getattr(client, method)(f"{BASE}{path}", **({"json": body} if body else {}))
    assert r.status_code == 503 and r.json() == {"error": {"message": "Database is unavailable"}}
    assert "secret" not in r.text


def test_unexpected_error_is_hidden(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.database import get_database
    from app.main import app
    from app.repositories.investigation_repository import InvestigationRepository

    def boom(*_a, **_k):
        raise RuntimeError("secret internals /srv/app.py")

    monkeypatch.setattr(InvestigationRepository, "get_investigations", boom)
    app.dependency_overrides[get_database] = lambda: db
    try:
        r = TestClient(app, raise_server_exceptions=False).get(BASE)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500 and "secret" not in r.text and "Traceback" not in r.text
