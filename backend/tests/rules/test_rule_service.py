import pytest

from app.services.rule_service import (
    PROTECTED_RULE_IDS,
    InvalidConditionError,
    InvalidRuleDataError,
    InvalidSeverityError,
    InvalidStatusError,
    RuleAlreadyExistsError,
    RuleNotFoundError,
    RuleProtectedError,
)
from tests.rules.conftest import rule_payload


def test_create_and_get(service):
    created = service.create_rule(rule_payload())
    assert created.rule_id == "AUTH-004"
    assert service.get_rule("AUTH-004").conditions["threshold"] == 10


def test_server_generates_timestamps(service):
    rule = service.create_rule({**rule_payload(), "created_at": "2001-01-01T00:00:00Z", "updated_at": "2001-01-01T00:00:00Z"})
    assert rule.created_at.year >= 2026


def test_duplicate_rejected(service):
    service.create_rule(rule_payload())
    with pytest.raises(RuleAlreadyExistsError):
        service.create_rule(rule_payload())


def test_get_missing(service):
    with pytest.raises(RuleNotFoundError):
        service.get_rule("NOPE-001")


def test_update_valid(service):
    created = service.create_rule(rule_payload())
    updated = service.update_rule("AUTH-004", {
        "name": "New name", "severity": "critical",
        "conditions": {"event_type": "authentication", "status": "failed", "threshold": 20, "window_minutes": 15},
    })
    assert (updated.name, updated.severity, updated.conditions["threshold"]) == ("New name", "critical", 20)
    assert updated.rule_id == "AUTH-004"
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at


def test_update_invalid_does_not_change_rule(service):
    service.create_rule(rule_payload())
    with pytest.raises(InvalidConditionError):
        service.update_rule("AUTH-004", {"conditions": {"event_type": "authentication", "threshold": 0, "window_minutes": 5}})
    with pytest.raises(InvalidSeverityError):
        service.update_rule("AUTH-004", {"severity": "urgent"})
    with pytest.raises(InvalidRuleDataError):
        service.update_rule("AUTH-004", {})
    with pytest.raises(InvalidRuleDataError):
        service.update_rule("AUTH-004", {"rule_id": "AUTH-999"})
    with pytest.raises(InvalidRuleDataError):
        service.update_rule("AUTH-004", {"created_at": "2001-01-01T00:00:00Z"})
    assert service.get_rule("AUTH-004").severity == "high"
    assert service.get_rule("AUTH-004").conditions["threshold"] == 10


def test_update_missing(service):
    with pytest.raises(RuleNotFoundError):
        service.update_rule("NOPE-001", {"name": "x"})


def test_enable_disable(service):
    service.create_rule(rule_payload())
    assert service.set_enabled("AUTH-004", False).enabled is False
    assert service.set_enabled("AUTH-004", True).enabled is True
    with pytest.raises(InvalidStatusError):
        service.set_enabled("AUTH-004", "false")
    with pytest.raises(RuleNotFoundError):
        service.set_enabled("NOPE-001", True)


def test_delete(service):
    service.create_rule(rule_payload())
    service.delete_rule("AUTH-004")
    with pytest.raises(RuleNotFoundError):
        service.get_rule("AUTH-004")
    with pytest.raises(RuleNotFoundError):
        service.delete_rule("AUTH-004")


def test_protected_rules_need_force(seeded, service):
    with pytest.raises(RuleProtectedError):
        service.delete_rule("AUTH-001")
    assert service.get_rule("AUTH-001")
    service.delete_rule("AUTH-001", force=True)
    with pytest.raises(RuleNotFoundError):
        service.get_rule("AUTH-001")


def test_protected_ids_match_seed_script(seed_module):
    assert PROTECTED_RULE_IDS == {r.rule_id for r in seed_module.build_rules()}


def test_list_pagination_and_limits(service):
    for i in range(1, 6):
        service.create_rule(rule_payload(rule_id=f"AUTH-{100 + i}"))
    page = service.list_rules(page=2, limit=2)
    assert [r.rule_id for r in page.rules] == ["AUTH-103", "AUTH-104"]
    assert (page.total, page.page, page.limit) == (5, 2, 2)
    assert service.list_rules(page=9, limit=2).rules == []
    for bad in ({"limit": 101}, {"limit": 0}, {"page": 0}):
        with pytest.raises(InvalidRuleDataError):
            service.list_rules(**bad)


def test_service_has_no_http_or_mongo_code():
    import ast
    from pathlib import Path

    import app.services.rule_service as module

    tree = ast.parse(Path(module.__file__).read_text())
    imported = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [m for m in imported if m.startswith(("fastapi", "starlette", "pymongo"))]
    assert not {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)} & {"eval", "exec", "compile"}
