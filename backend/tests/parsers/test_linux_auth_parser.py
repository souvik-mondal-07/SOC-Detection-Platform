from datetime import datetime, timezone

import pytest

from app.parsers.base import ParseError
from app.parsers.linux_auth_parser import LinuxAuthParser
from tests.parsers.conftest import raw_lines

parser = LinuxAuthParser(reference_time=datetime(2026, 10, 3, tzinfo=timezone.utc))
PREFIX = "Oct  2 10:15:23 server sshd[1234]: "


def test_failed_login():
    e = parser.parse(PREFIX + "Failed password for test_user from 192.168.1.20 port 54321 ssh2")
    assert (e["source"], e["event_type"], e["action"], e["status"]) == ("linux_auth", "authentication", "login", "failed")
    assert (e["username"], e["source_ip"]) == ("test_user", "192.168.1.20")
    assert e["timestamp"] == datetime(2026, 10, 2, 10, 15, 23, tzinfo=timezone.utc)
    assert e["message"].startswith("Failed password for test_user")
    assert e["metadata"]["source_port"] == 54321 and e["metadata"]["hostname"] == "server" and e["metadata"]["pid"] == 1234
    assert e["metadata"]["timestamp_year_assumed"] is True


def test_successful_login():
    e = parser.parse("Oct  2 10:17:12 server sshd[1234]: Accepted publickey for test_user from 192.168.1.20 port 54321 ssh2")
    assert e["status"] == "success" and e["username"] == "test_user"
    assert e["metadata"]["auth_method"] == "publickey"


def test_failed_password_for_invalid_user():
    e = parser.parse(PREFIX + "Failed password for invalid user ghost from 10.0.0.15 port 22 ssh2")
    assert (e["status"], e["username"], e["metadata"]["reason"]) == ("failed", "ghost", "invalid_user")


def test_invalid_user_line():
    e = parser.parse(PREFIX + "Invalid user demo_user from 10.0.0.15 port 40112")
    assert (e["status"], e["username"], e["source_ip"], e["metadata"]["reason"]) == ("failed", "demo_user", "10.0.0.15", "invalid_user")


def test_blocked_user():
    e = parser.parse(PREFIX + "User blocked_user from 10.0.0.15 not allowed because listed in DenyUsers")
    assert e["status"] == "blocked" and e["username"] == "blocked_user"


def test_pam_failure_without_user_keeps_what_exists():
    e = parser.parse("Oct  2 10:15:23 server sshd[9]: pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=192.168.1.20")
    assert e["status"] == "failed" and e["source_ip"] == "192.168.1.20" and e["username"] is None


def test_year_rolls_back_for_future_dates():
    jan = LinuxAuthParser(reference_time=datetime(2027, 1, 2, tzinfo=timezone.utc))
    assert jan.parse("Dec 31 23:59:59 h sshd[1]: Accepted password for u from 10.0.0.1 port 1 ssh2")["timestamp"].year == 2026


def test_rfc3339_timestamp():
    e = parser.parse("2026-10-02T10:15:23.123456+00:00 server sshd[1]: Accepted password for u from 10.0.0.1 port 1 ssh2")
    assert e["timestamp"].hour == 10 and "timestamp_year_assumed" not in e["metadata"]


@pytest.mark.parametrize("line", [
    "this is not a valid authentication log",
    "",
    "   ",
    "Oct  2 10:15:23 server",
    None,
    123,
])
def test_malformed_lines(line):
    with pytest.raises(ParseError) as exc:
        parser.parse(line)
    assert exc.value.code == "invalid_log"


def test_unsupported_syslog_line():
    with pytest.raises(ParseError) as exc:
        parser.parse(PREFIX + "Received disconnect from 10.0.0.15 port 22:11: bye")
    assert exc.value.code == "unsupported_event"


def test_impossible_date():
    with pytest.raises(ParseError) as exc:
        parser.parse("Feb 31 10:00:00 h sshd[1]: Accepted password for u from 10.0.0.1 port 1 ssh2")
    assert exc.value.field == "timestamp"


def test_sample_file_parses_completely():
    lines = raw_lines("linux_auth.log")
    assert [parser.parse(line)["status"] for line in lines] == ["failed", "failed", "failed", "failed", "blocked", "success", "success"]


def test_raw_password_never_in_output():
    e = parser.parse(PREFIX + "Failed password for test_user from 192.168.1.20 port 54321 ssh2")
    assert not any("password" in key.lower() for key in e["metadata"])
