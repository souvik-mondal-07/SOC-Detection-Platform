import pytest

from app.core.errors import DuplicateRecordError
from app.models.alert import Alert
from app.models.common import utc_now


def alert(n: int, **kw) -> Alert:
    data = dict(alert_id=f"ALT-20261007-{n:06d}", rule_id="AUTH-001", title="t", description="d", severity="high",
                source_ip="192.168.1.20", event_ids=[f"evt_{n}"])
    return Alert(**{**data, **kw})


def test_create_get_and_duplicate_id(alert_repo):
    alert_repo.create_alert(alert(1))
    assert alert_repo.get_alert_by_id("ALT-20261007-000001").rule_id == "AUTH-001"
    assert alert_repo.get_alert_by_id("ALT-20261007-999999") is None
    with pytest.raises(DuplicateRecordError):
        alert_repo.create_alert(alert(1))


def test_filters_and_pagination(alert_repo):
    alert_repo.create_alert(alert(1))
    alert_repo.create_alert(alert(2, severity="low", rule_id="WEB-001", source_ip=None))
    alert_repo.create_alert(alert(3))
    assert alert_repo.get_alerts(severity="high")[1] == 2
    assert alert_repo.get_alerts(rule_id="WEB-001")[1] == 1
    assert alert_repo.get_alerts(source_ip="192.168.1.20")[1] == 2
    page, total = alert_repo.get_alerts(skip=1, limit=1)
    assert total == 3 and len(page) == 1
    with pytest.raises(ValueError):
        alert_repo.get_alerts(limit=101)


def test_update_alert(alert_repo):
    alert_repo.create_alert(alert(1))
    assert alert_repo.update_alert("ALT-20261007-000001", {"status": "investigating"}).status == "investigating"
    assert alert_repo.update_alert("ALT-20261007-000404", {"status": "resolved"}) is None
    with pytest.raises(ValueError):
        alert_repo.update_alert("ALT-20261007-000001", {"alert_id": "x"})


def test_next_alert_id_sequence(alert_repo):
    now = utc_now()
    first = alert_repo.next_alert_id(now)
    assert first == f"ALT-{now:%Y%m%d}-000001"
    alert_repo.create_alert(alert(1, alert_id=first))
    assert alert_repo.next_alert_id(now).endswith("-000002")


def test_indexes_unique_and_idempotent(alert_repo):
    alert_repo.ensure_indexes()
    names = set(alert_repo._collection.index_information())
    assert {"uq_alert_id", "ix_created_at", "ix_status_created_at", "ix_severity_created_at",
            "ix_rule_id_created_at", "ix_source_ip_created_at"} <= names
    assert alert_repo._collection.index_information()["uq_alert_id"].get("unique")
