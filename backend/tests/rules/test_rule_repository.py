import pytest

from app.core.errors import DuplicateRecordError
from app.models.rule import DetectionRule
from app.repositories.detection_rule_repository import MAX_PAGE_LIMIT
from tests.rules.conftest import rule_payload


def make(rule_id="AUTH-004", **kw) -> DetectionRule:
    return DetectionRule(**rule_payload(rule_id=rule_id, **kw))


def test_create_and_get(repo):
    repo.create_rule(make())
    assert repo.get_rule("AUTH-004").name == "Repeated Authentication Failures"
    assert repo.get_rule("NOPE-001") is None


def test_duplicate_rule_id_rejected(repo):
    repo.create_rule(make())
    with pytest.raises(DuplicateRecordError):
        repo.create_rule(make())


def test_indexes_present_and_not_duplicated(repo, mongo_db):
    names = set(mongo_db["detection_rules"].index_information())
    assert {"uq_rule_id", "ix_category", "ix_severity", "ix_enabled"} <= names
    assert mongo_db["detection_rules"].index_information()["uq_rule_id"]["unique"] is True
    repo.ensure_indexes()
    repo.ensure_indexes()
    assert set(mongo_db["detection_rules"].index_information()) == names


@pytest.fixture
def populated(repo):
    rows = [
        ("AUTH-004", "authentication", "high", True, "Brute force"),
        ("AUTH-005", "authentication", "low", False, "Odd login"),
        ("WEB-004", "web", "high", True, "Web scan"),
        ("WEB-005", "web", "medium", False, "Web errors"),
        ("NET-004", "network", "critical", True, "Port sweep"),
    ]
    for rule_id, category, severity, enabled, name in rows:
        repo.create_rule(make(rule_id, category=category, severity=severity, enabled=enabled, name=name))
    return repo


@pytest.mark.parametrize("filters,expected", [
    ({}, ["AUTH-004", "AUTH-005", "NET-004", "WEB-004", "WEB-005"]),
    ({"category": "web"}, ["WEB-004", "WEB-005"]),
    ({"severity": "high"}, ["AUTH-004", "WEB-004"]),
    ({"enabled": True}, ["AUTH-004", "NET-004", "WEB-004"]),
    ({"enabled": False}, ["AUTH-005", "WEB-005"]),
    ({"category": "web", "severity": "high"}, ["WEB-004"]),
    ({"category": "authentication", "severity": "high", "enabled": True}, ["AUTH-004"]),
    ({"category": "web", "severity": "critical"}, []),
    ({"name": "SCAN"}, ["WEB-004"]),
    ({"name": ".*"}, []),  # escaped: not a regex
])
def test_filters(populated, filters, expected):
    rules, total = populated.get_rules(**filters)
    assert [r.rule_id for r in rules] == expected
    assert total == len(expected)


def test_pagination_slices_in_database_and_reports_total(populated):
    page1, total = populated.get_rules(skip=0, limit=2)
    page3, _ = populated.get_rules(skip=4, limit=2)
    assert [r.rule_id for r in page1] == ["AUTH-004", "AUTH-005"]
    assert [r.rule_id for r in page3] == ["WEB-005"]
    assert total == 5


def test_limit_bounds_enforced(populated):
    with pytest.raises(ValueError):
        populated.get_rules(limit=MAX_PAGE_LIMIT + 1)
    with pytest.raises(ValueError):
        populated.get_rules(limit=0)
    with pytest.raises(ValueError):
        populated.get_rules(skip=-1)


def test_update_keeps_rule_id_and_created_at_and_bumps_updated_at(repo):
    created = repo.create_rule(make())
    updated = repo.update_rule("AUTH-004", {"name": "Renamed"})
    assert updated.name == "Renamed"
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at
    with pytest.raises(ValueError):
        repo.update_rule("AUTH-004", {"rule_id": "AUTH-999"})
    assert repo.update_rule("NOPE-001", {"name": "x"}) is None


def test_set_enabled(repo):
    repo.create_rule(make())
    assert repo.set_enabled("AUTH-004", False).enabled is False
    assert repo.get_rule("AUTH-004").enabled is False
    assert repo.set_enabled("NOPE-001", True) is None


def test_delete(repo):
    repo.create_rule(make())
    assert repo.delete_rule("AUTH-004") is True
    assert repo.delete_rule("AUTH-004") is False
    assert repo.get_rule("AUTH-004") is None


def test_enabled_rules_for_engine_exclude_disabled(populated):
    assert {r.rule_id for r in populated.get_enabled_rules()} == {"AUTH-004", "NET-004", "WEB-004"}
