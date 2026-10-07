"""Validation of rule input (service level) and request schemas."""

import pytest
from pydantic import ValidationError

from app.models.rule_management import RuleCreateRequest, RuleStatusRequest, RuleUpdateRequest
from app.services.rule_service import (
    InvalidCategoryError,
    InvalidConditionError,
    InvalidRuleDataError,
    InvalidSeverityError,
    validate_conditions,
)
from tests.rules.conftest import rule_payload


def test_valid_create_request():
    assert RuleCreateRequest(**rule_payload()).rule_id == "AUTH-004"


@pytest.mark.parametrize("rule_id", ["", "auth-001", "AUTH001", "AUTH-1", "AUTH-001; DROP", "A-001", "X" * 40 + "-001"])
def test_bad_rule_id_rejected(rule_id):
    with pytest.raises(ValidationError):
        RuleCreateRequest(**rule_payload(rule_id=rule_id))


@pytest.mark.parametrize("field", ["rule_id", "name", "category", "description", "severity", "conditions"])
def test_missing_required_fields_rejected(field):
    data = rule_payload()
    del data[field]
    with pytest.raises(ValidationError):
        RuleCreateRequest(**data)


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name_rejected(name):
    with pytest.raises(ValidationError):
        RuleCreateRequest(**rule_payload(name=name))


@pytest.mark.parametrize("severity", ["urgent", "danger", "severe", "HIGH", ""])
def test_unsupported_severity_rejected(severity):
    with pytest.raises(ValidationError):
        RuleCreateRequest(**rule_payload(severity=severity))


def test_unsupported_category_rejected():
    with pytest.raises(ValidationError):
        RuleCreateRequest(**rule_payload(category="astrology"))


@pytest.mark.parametrize("category", ["authentication", "web", "network", "privilege", "system", "application", "correlation"])
def test_supported_categories(category):
    assert RuleCreateRequest(**rule_payload(category=category)).category.value == category


@pytest.mark.parametrize("value", ["yes", 1, "true", None])
def test_enabled_must_be_boolean(value):
    with pytest.raises(ValidationError):
        RuleCreateRequest(**rule_payload(enabled=value))
    with pytest.raises(ValidationError):
        RuleStatusRequest(enabled=value)


def test_client_timestamps_and_unknown_fields_rejected():
    for extra in ({"created_at": "2020-01-01T00:00:00Z"}, {"updated_at": "2020-01-01T00:00:00Z"}, {"script": "x"}):
        with pytest.raises(ValidationError):
            RuleCreateRequest(**rule_payload(**extra))


def test_update_request_cannot_change_rule_id():
    with pytest.raises(ValidationError):
        RuleUpdateRequest(rule_id="AUTH-999")


# -- conditions ---------------------------------------------------------------------------

def test_valid_conditions_accepted():
    validate_conditions({"event_type": "authentication", "status": "failed", "threshold": 3, "window_minutes": 5})
    validate_conditions({"event_type": "web"})


@pytest.mark.parametrize("conditions", [
    {"event_type": "authentication", "threshold": 0, "window_minutes": 5},
    {"event_type": "authentication", "threshold": -3, "window_minutes": 5},
    {"event_type": "authentication", "threshold": 1001, "window_minutes": 5},
    {"event_type": "authentication", "threshold": "5", "window_minutes": 5},
    {"event_type": "authentication", "threshold": 5, "window_minutes": 0},
    {"event_type": "authentication", "threshold": 5, "window_minutes": 1441},
    {"event_type": "authentication", "threshold": 5},  # threshold needs a window
    {"event_type": "authentication", "window_minutes": 5},  # window needs a threshold
    {"event_type": "authentication", "correlation_field": "source_ip"},  # correlation needs a stateful rule
    {"event_type": "authentication", "threshold": 5, "window_minutes": 5, "correlation_field": "hostname"},
    {"event_type": "nonsense"},
    {"status": "exploded"},
    {"threshold": 5, "window_minutes": 5},  # would match every event
    {},
    {"event_type": "authentication", "run": "__import__('os').system('id')"},  # unknown key
    {"event_type": "authentication", "expression": "1 == 1"},
    {"event_type": "authentication", "$where": "sleep(1000)"},
    {"event_type": "web", "metadata": {"a.b": 1}},
])
def test_invalid_conditions_rejected(conditions):
    with pytest.raises(InvalidConditionError):
        validate_conditions(conditions)


def test_condition_error_does_not_echo_submitted_values():
    secret = "S3cretValue_do_not_echo"
    with pytest.raises(InvalidConditionError) as caught:
        validate_conditions({"event_type": "authentication", "status": secret})
    assert secret not in str(caught.value)


# -- service-level mapping to error codes -------------------------------------------------

def test_service_error_codes(service):
    with pytest.raises(InvalidSeverityError):
        service.create_rule({**rule_payload(), "severity": "urgent"})
    with pytest.raises(InvalidCategoryError):
        service.create_rule({**rule_payload(), "category": "astrology"})
    with pytest.raises(InvalidConditionError):
        service.create_rule({**rule_payload(), "conditions": {"threshold": 0}})
    with pytest.raises(InvalidRuleDataError):
        service.create_rule({**rule_payload(), "name": ""})
