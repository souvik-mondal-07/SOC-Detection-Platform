from datetime import datetime, timezone

import pytest

from app.parsers.base import ParseError
from app.parsers.web_log_parser import WebLogParser
from tests.parsers.conftest import raw_lines

parser = WebLogParser()
GET_404 = '192.168.1.20 - - [02/Oct/2026:10:20:10 +0000] "GET /admin HTTP/1.1" 404 512'


def test_get_404():
    e = parser.parse(GET_404)
    assert (e["source"], e["event_type"], e["action"], e["status"]) == ("web_application", "web", "http_request", "failed")
    assert e["source_ip"] == "192.168.1.20" and e["message"] == "GET /admin HTTP/1.1 404"
    assert e["metadata"] == {"method": "GET", "path": "/admin", "http_status": 404, "response_size": 512, "protocol": "HTTP/1.1"}
    assert e["timestamp"] == datetime(2026, 10, 2, 10, 20, 10, tzinfo=timezone.utc)
    assert "username" not in e


def test_post_200():
    e = parser.parse('10.0.0.15 - - [02/Oct/2026:10:20:15 +0000] "POST /login HTTP/1.1" 200 128')
    assert e["metadata"]["method"] == "POST" and e["status"] == "success"


def test_redirect_is_success_and_5xx_failed():
    assert parser.parse(GET_404.replace("404", "302"))["status"] == "success"
    assert parser.parse(GET_404.replace("404", "500"))["status"] == "failed"


def test_timezone_offset_converted_to_utc():
    e = parser.parse('10.0.0.15 - - [02/Oct/2026:12:20:10 +0200] "GET / HTTP/1.1" 200 1')
    assert e["timestamp"].hour == 10


def test_dash_size_omitted_and_combined_format_agent():
    e = parser.parse('10.0.0.15 - - [02/Oct/2026:10:21:09 +0000] "GET /x HTTP/1.1" 404 - "-" "test-client/1.0"')
    assert "response_size" not in e["metadata"] and e["metadata"]["user_agent"] == "test-client/1.0"


def test_404_is_not_labelled_malicious():
    e = parser.parse(GET_404)
    assert not {"severity", "alert", "suspicious", "malicious"} & (set(e) | set(e["metadata"]))


@pytest.mark.parametrize("line", [
    "not a log line",
    "",
    '192.168.1.20 - - [02/Oct/2026:10:20:10 +0000] "GET /admin HTTP/1.1" abc 512',
    "192.168.1.20 - - [bad] GET /admin 404 512",
    None,
])
def test_malformed(line):
    with pytest.raises(ParseError):
        parser.parse(line)


def test_bad_request_line_and_timestamp_and_status():
    for line, field in [
        ('1.1.1.1 - - [02/Oct/2026:10:20:10 +0000] "-" 408 0', "request"),
        ('1.1.1.1 - - [32/Oct/2026:10:20:10 +0000] "GET / HTTP/1.1" 200 0', "timestamp"),
        ('1.1.1.1 - - [02/Foo/2026:10:20:10 +0000] "GET / HTTP/1.1" 200 0', "timestamp"),
        ('1.1.1.1 - - [02/Oct/2026:10:20:10 +0000] "GET / HTTP/1.1" 999 0', "http_status"),
    ]:
        with pytest.raises(ParseError) as exc:
            parser.parse(line)
        assert exc.value.field == field


def test_sample_file_parses_completely():
    assert len([parser.parse(line) for line in raw_lines("web_access.log")]) == 6
