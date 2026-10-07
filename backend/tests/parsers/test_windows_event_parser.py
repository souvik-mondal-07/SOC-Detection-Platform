import json

import pytest

from app.parsers.base import ParseError
from app.parsers.windows_event_parser import WindowsEventParser
from tests.parsers.conftest import raw_json

parser = WindowsEventParser()
EVENT = {"EventID": 4625, "TimeCreated": "2026-10-02T10:25:00Z", "Computer": "WIN-SERVER",
         "TargetUserName": "test_user", "IpAddress": "192.168.1.20", "Message": "An account failed to log on."}


def test_4625_failed_logon():
    e = parser.parse(EVENT)
    assert (e["source"], e["event_type"], e["action"], e["status"]) == ("windows_event", "authentication", "login", "failed")
    assert (e["username"], e["source_ip"], e["timestamp"]) == ("test_user", "192.168.1.20", "2026-10-02T10:25:00Z")
    assert e["metadata"] == {"event_id": 4625, "computer": "WIN-SERVER"}


def test_4624_successful_logon():
    assert parser.parse({**EVENT, "EventID": 4624})["status"] == "success"


def test_json_string_and_numeric_string_id():
    assert parser.parse(json.dumps({**EVENT, "EventID": "4624"}))["status"] == "success"


def test_missing_optional_fields_are_not_invented():
    e = parser.parse({"EventID": 4625})
    assert e["username"] is None and e["source_ip"] is None and e["timestamp"] is None
    assert e["metadata"] == {"event_id": 4625} and e["message"]


def test_placeholder_ip_dash_is_dropped():
    assert parser.parse({**EVENT, "IpAddress": "-"})["source_ip"] is None


def test_unsupported_event_id():
    with pytest.raises(ParseError) as exc:
        parser.parse({**EVENT, "EventID": 4688})
    assert exc.value.code == "unsupported_event"


@pytest.mark.parametrize("raw, code", [
    ({}, "missing_field"),
    ({"EventID": "abc"}, "invalid_field"),
    ({"EventID": True}, "missing_field"),
    ("{not json", "invalid_log"),
    ("[1, 2]", "invalid_log"),
    (None, "invalid_log"),
])
def test_malformed(raw, code):
    with pytest.raises(ParseError) as exc:
        parser.parse(raw)
    assert exc.value.code == code


def test_sample_file_parses_completely():
    assert [parser.parse(r)["status"] for r in raw_json("windows_events.json")] == ["failed", "failed", "success", "success"]
