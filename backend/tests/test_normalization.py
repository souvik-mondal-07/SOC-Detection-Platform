import pytest
from pydantic import ValidationError

from app.models.event import EventCreate, EventQuery
from app.models.normalization import (
    normalize_action,
    normalize_event_type,
    normalize_source,
    normalize_status,
    prepare_timestamp,
)


@pytest.mark.parametrize("raw", ["failed", "FAILED", "Failed", " failed ", "Failure", "FAIL"])
def test_status_failed_variants(raw):
    assert normalize_status(raw) == "failed"


@pytest.mark.parametrize("raw,expected", [
    ("SUCCESS", "success"), ("Success", "success"), ("successful", "success"), ("Succeeded", "success"),
    ("BLOCKED", "blocked"), ("block", "blocked"), ("Unknown", "unknown"), ("n/a", "unknown"),
])
def test_status_other_variants(raw, expected):
    assert normalize_status(raw) == expected


@pytest.mark.parametrize("raw", ["Authentication", "AUTH", "authentication", " auth "])
def test_event_type_authentication_variants(raw):
    assert normalize_event_type(raw) == "authentication"


@pytest.mark.parametrize("raw,expected", [("PRIV", "privilege"), ("Net", "network"), ("SYS", "system"), ("Application", "application")])
def test_event_type_aliases(raw, expected):
    assert normalize_event_type(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Linux Auth", "linux_auth"), ("LINUX-AUTH", "linux_auth"), ("windows", "windows_event"),
    ("Web", "web_application"), ("app", "application"), ("NETWORK", "network"),
])
def test_source_variants(raw, expected):
    assert normalize_source(raw) == expected


def test_action_becomes_lowercase_snake_case():
    assert normalize_action("Privilege Change") == "privilege_change"
    assert normalize_action("  LOGIN ") == "login"


def test_unknown_values_are_not_guessed():
    # Normalisation never invents a mapping; the schema rejects these afterwards.
    assert normalize_status("denied") == "denied"
    assert normalize_event_type("banana") == "banana"
    assert normalize_source("syslog") == "syslog"


def test_non_strings_pass_through_unchanged():
    assert normalize_status(5) == 5
    assert normalize_source(None) is None


def test_username_case_is_preserved_and_message_is_trimmed_not_altered():
    event = EventCreate(source="linux_auth", event_type="auth", action="login", username=" Test_User ",
                        message="  Failed   password  ")
    assert event.username == "Test_User"
    assert event.message == "Failed   password"  # inner spacing kept


def test_blank_optional_fields_become_none_and_missing_status_is_unknown():
    event = EventCreate(source="network", event_type="network", action="connection", message="m",
                        username="  ", source_ip="", status=None)
    assert event.username is None and event.source_ip is None
    assert event.status == "unknown"


def test_over_long_message_is_rejected_not_truncated():
    with pytest.raises(ValidationError):
        EventCreate(source="network", event_type="network", action="connection", message="x" * 1001)


@pytest.mark.parametrize("value", [1696243523, "1696243523", "2026-10-02", "2026-10-02T10:15:23", "yesterday", "", True])
def test_malformed_or_ambiguous_timestamps_rejected(value):
    with pytest.raises(ValidationError):
        EventCreate(source="network", event_type="network", action="connection", message="m", timestamp=value)


@pytest.mark.parametrize("value,expected", [
    ("2026-10-02T10:15:23Z", "2026-10-02T10:15:23+00:00"),
    ("2026-10-02T12:15:23+02:00", "2026-10-02T10:15:23+00:00"),
    ("2026-10-02T10:15:23.250Z", "2026-10-02T10:15:23.250000+00:00"),
    ("2026-10-02 10:15:23Z", "2026-10-02T10:15:23+00:00"),
])
def test_valid_timestamps_normalised_to_utc(value, expected):
    event = EventCreate(source="network", event_type="network", action="connection", message="m", timestamp=value)
    assert event.timestamp.isoformat() == expected


def test_prepare_timestamp_passes_none_through():
    assert prepare_timestamp(None) is None


def test_query_filters_are_normalised_too():
    query = EventQuery(status="FAILED", event_type="AUTH", source="Linux Auth", source_ip="192.168.1.20")
    assert (query.status, query.event_type, query.source) == ("failed", "authentication", "linux_auth")
    with pytest.raises(ValidationError):
        EventQuery(status="banana")
