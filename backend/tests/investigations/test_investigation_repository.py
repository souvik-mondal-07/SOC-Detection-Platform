import pytest

from app.core.errors import DuplicateRecordError
from app.models.common import utc_now
from app.models.investigation import Investigation, InvestigationNote


def make(investigation_id="INV-20261014-000001", **kw):
    return Investigation(investigation_id=investigation_id, title="t", alert_ids=["a1"], **kw)


def test_indexes_include_alert_ids_and_are_unique_on_id(db, investigation_repo):
    names = {i["name"] for i in db["investigations"].list_indexes()}
    assert {"uq_investigation_id", "ix_status_created_at", "ix_created_at", "ix_alert_ids"} <= names
    investigation_repo.create_investigation(make())
    with pytest.raises(DuplicateRecordError):
        investigation_repo.create_investigation(make())


def test_next_id_continues_the_day_sequence(investigation_repo):
    now = utc_now()
    first = investigation_repo.next_investigation_id(now)
    assert first == f"INV-{now:%Y%m%d}-000001"
    investigation_repo.create_investigation(make(first))
    assert investigation_repo.next_investigation_id(now) == f"INV-{now:%Y%m%d}-000002"


def test_pagination_bounds(investigation_repo):
    with pytest.raises(ValueError):
        investigation_repo.get_investigations(limit=0)
    with pytest.raises(ValueError):
        investigation_repo.get_investigations(limit=101)
    with pytest.raises(ValueError):
        investigation_repo.get_investigations(skip=-1)


def test_add_alert_ids_never_stores_duplicates(investigation_repo):
    investigation_repo.create_investigation(make())
    assert investigation_repo.add_alert_ids("INV-20261014-000001", ["a1", "a2", "a2"])
    assert investigation_repo.get_investigation_by_id("INV-20261014-000001").alert_ids == ["a1", "a2"]
    assert investigation_repo.add_alert_ids("missing", ["a3"]) is False


def test_remove_alert_id_keeps_last_alert(investigation_repo):
    investigation_repo.create_investigation(make())
    assert investigation_repo.remove_alert_id("INV-20261014-000001", "a1") is False  # last alert
    investigation_repo.add_alert_ids("INV-20261014-000001", ["a2"])
    assert investigation_repo.remove_alert_id("INV-20261014-000001", "a1") is True
    assert investigation_repo.remove_alert_id("INV-20261014-000001", "a1") is False  # no longer linked


def test_add_note_and_missing(investigation_repo):
    investigation_repo.create_investigation(make())
    assert investigation_repo.add_note("INV-20261014-000001", InvestigationNote(text="hello"))
    assert investigation_repo.add_note("missing", InvestigationNote(text="x")) is False
    assert [n.text for n in investigation_repo.get_investigation_by_id("INV-20261014-000001").notes] == ["hello"]
