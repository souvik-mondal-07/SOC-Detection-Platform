import json

import pytest

from app.parsers.base import ParseError
from app.parsers.network_log_parser import NetworkLogParser
from tests.parsers.conftest import raw_json

parser = NetworkLogParser()
EVENT = {"timestamp": "2026-10-02T10:30:00Z", "source_ip": "192.168.1.20", "destination_ip": "192.168.1.10",
         "source_port": 54321, "destination_port": 22, "protocol": "TCP", "action": "connection", "status": "allowed"}


def test_valid_event():
    e = parser.parse(EVENT)
    assert (e["source"], e["event_type"], e["action"], e["status"], e["source_ip"]) == ("network", "network", "connection", "success", "192.168.1.20")
    assert e["metadata"] == {"destination_ip": "192.168.1.10", "source_port": 54321, "destination_port": 22, "protocol": "TCP"}


def test_status_mapping():
    assert parser.parse({**EVENT, "status": "denied"})["status"] == "blocked"
    assert parser.parse({**EVENT, "status": "weird"})["status"] == "unknown"
    assert parser.parse({k: v for k, v in EVENT.items() if k != "status"})["status"] == "unknown"


def test_protocol_uppercased_and_optional_fields():
    e = parser.parse({"source_ip": "10.0.0.15", "destination_ip": "10.0.0.1", "destination_port": "80", "protocol": "tcp"})
    assert e["metadata"]["protocol"] == "TCP" and e["metadata"]["destination_port"] == 80
    assert e["timestamp"] is None and e["action"] == "connection" and "source_port" not in e["metadata"]


def test_json_string_and_csv_line():
    assert parser.parse(json.dumps(EVENT))["source_ip"] == "192.168.1.20"
    e = parser.parse("2026-10-02T10:30:00Z,192.168.1.20,192.168.1.10,54321,22,TCP,connection,allowed")
    assert e["status"] == "success" and e["metadata"]["destination_port"] == 22


@pytest.mark.parametrize("missing", ["source_ip", "destination_ip", "destination_port", "protocol"])
def test_missing_required_field(missing):
    with pytest.raises(ParseError) as exc:
        parser.parse({k: v for k, v in EVENT.items() if k != missing})
    assert (exc.value.code, exc.value.field) == ("missing_field", missing)


@pytest.mark.parametrize("raw", ["{not json", "a,b,c", "", [1], None, 5])
def test_malformed_input(raw):
    with pytest.raises(ParseError):
        parser.parse(raw)


def test_invalid_ports_and_protocol():
    for override in ({"destination_port": 70000}, {"destination_port": "x"}, {"source_port": -1}, {"protocol": "TCP; DROP"}):
        with pytest.raises(ParseError) as exc:
            parser.parse({**EVENT, **override})
        assert exc.value.code == "invalid_field"


def test_no_scan_detection_fields():
    assert set(parser.parse(EVENT)) == {"timestamp", "source", "event_type", "action", "status", "source_ip", "message", "metadata"}


def test_sample_file_parses_completely():
    assert [parser.parse(r)["status"] for r in raw_json("network_events.json")] == ["success", "blocked", "success"]
