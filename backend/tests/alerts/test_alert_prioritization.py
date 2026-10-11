"""Ordering, filtering and pagination by priority (repository and API)."""

from datetime import timedelta

import pytest

from app.models.alert import Alert
from app.models.common import utc_now

BASE = utc_now() - timedelta(days=1)
_SEVERITY_OF = {25: "low", 55: "medium", 75: "high", 82: "high", 95: "critical"}


def put(repo, n, score, minutes=0, **kw):
    data = dict(alert_id=f"ALT-20261007-{n:06d}", rule_id="AUTH-001", title="t", description="d",
                severity=_SEVERITY_OF.get(score, "high"), priority_score=score, source_ip="192.168.1.20",
                event_ids=[f"evt_{n}"], created_at=BASE + timedelta(minutes=minutes), updated_at=BASE + timedelta(minutes=minutes))
    return repo.create_alert(Alert(**{**data, **kw}))


@pytest.fixture
def seeded(alert_repo):
    put(alert_repo, 1, 25, 5)
    put(alert_repo, 2, 82, 1)
    put(alert_repo, 3, 95, 2)
    put(alert_repo, 4, 75, 3)
    put(alert_repo, 5, 55, 4)
    put(alert_repo, 6, 82, 9)  # same score as #2 but newer
    return alert_repo


def ids(alerts):
    return [a.alert_id[-1] for a in alerts]


def test_default_order_priority_desc_then_newest(seeded):
    alerts, total = seeded.get_alerts()
    assert total == 6 and [a.priority_score for a in alerts] == [95, 82, 82, 75, 55, 25]
    assert ids(alerts) == ["3", "6", "2", "4", "5", "1"]  # equal 82s: newest (#6) first


def test_priority_filters_at_db_level(seeded):
    assert ids(seeded.get_alerts(priority_min=80)[0]) == ["3", "6", "2"]
    assert ids(seeded.get_alerts(priority_max=55)[0]) == ["5", "1"]
    assert ids(seeded.get_alerts(priority_min=55, priority_max=82)[0]) == ["6", "2", "4", "5"]
    assert seeded.get_alerts(priority_min=96)[1] == 0
    assert seeded.get_alerts(severity="high", priority_min=80)[1] == 2


@pytest.mark.parametrize("kw", [{"priority_min": -1}, {"priority_max": 101}, {"priority_min": 90, "priority_max": 10}])
def test_invalid_priority_bounds(seeded, kw):
    with pytest.raises(ValueError):
        seeded.get_alerts(**kw)


def test_priority_indexes(alert_repo):
    names = set(alert_repo.ensure_indexes())
    assert {"ix_priority_created_at", "ix_status_priority_created_at"} <= names


def test_api_order_fields_and_filters(client, db, seeded):
    body = client.get("/api/v1/alerts").json()
    assert [a["priority_score"] for a in body["alerts"]] == [95, 82, 82, 75, 55, 25]
    assert {"severity", "priority_score", "status"} <= set(body["alerts"][0]) and "priority_reason" in body["alerts"][0]
    assert client.get("/api/v1/alerts?priority_min=80").json()["total"] == 3
    assert client.get("/api/v1/alerts?priority_max=55").json()["total"] == 2
    assert client.get("/api/v1/alerts?severity=high&status=open").json()["total"] == 3
    assert client.get("/api/v1/alerts?severity=high&priority_min=80&priority_max=90").json()["total"] == 2
    for query in ("priority_min=-1", "priority_max=101", "priority_min=x", "priority_min=90&priority_max=10"):
        assert client.get(f"/api/v1/alerts?{query}").status_code == 422, query


def test_api_pagination(client, db, seeded):
    page1 = client.get("/api/v1/alerts?page=1&limit=4").json()
    page2 = client.get("/api/v1/alerts?page=2&limit=4").json()
    assert page1["total"] == 6 and page1["count"] == 4 and page2["count"] == 2
    assert [a["priority_score"] for a in page1["alerts"] + page2["alerts"]] == [95, 82, 82, 75, 55, 25]
    assert client.get("/api/v1/alerts?limit=100").status_code == 200
    assert client.get("/api/v1/alerts?limit=101").status_code == 422


def test_generated_alert_api_includes_priority(client, db, burst):
    created = client.post(f"/api/v1/alerts/generate/{burst[-1].event_id}").json()["alerts"][0]
    assert created["priority_score"] == 83
    listed = client.get("/api/v1/alerts").json()["alerts"][0]
    assert listed["severity"] == "high" and listed["priority_score"] == 83 and listed["priority_reason"]
    detail = client.get(f"/api/v1/alerts/{listed['alert_id']}").json()["alert"]
    assert detail["priority_score"] == 83
    # a client cannot supply priority or severity
    assert client.post("/api/v1/alerts/generate", json={"event_ids": ["evt_1"], "priority_score": 100}).status_code == 422
