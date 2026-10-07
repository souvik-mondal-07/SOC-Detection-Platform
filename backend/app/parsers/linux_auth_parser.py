"""Linux authentication (sshd / PAM syslog) lines.

Supported:
  Failed <method> for [invalid user] <user> from <ip> [port N] ...  -> login / failed
  Accepted <method> for <user> from <ip> [port N] ...               -> login / success
  Invalid user <user> from <ip> [port N]                            -> login / failed
  User <user> from <ip> not allowed because ...                     -> login / blocked
  refused connect from <host> (<ip>)                                -> login / blocked
  pam_unix(...): authentication failure; ... rhost=<ip> user=<user> -> login / failed

Syslog lines carry no year or time zone. The year is inferred (the most recent
past occurrence) and UTC is assumed; both are recorded in metadata. RFC 3339
timestamps (rsyslog high-precision format) are used as they are.
"""

import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.parsers.base import BaseParser, ParsedEvent, ParseError, clip_message, require_text

_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}

_SYSLOG = re.compile(
    r"^(?P<ts>(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})"
    r"|\d{4}-\d{2}-\d{2}T\S+)"
    r"\s+(?P<host>\S+)\s+(?P<proc>[\w./-]+)(?:\[(?P<pid>\d+)\])?:\s+(?P<msg>.+)$"
)

_IP = r"[0-9A-Fa-f:.]+"
_PORT = r"(?: port (?P<port>\d+))?"
_FAILED = re.compile(rf"^Failed (?P<method>\S+) for (?P<invalid>invalid user )?(?P<user>\S+) from (?P<ip>{_IP}){_PORT}")
_ACCEPTED = re.compile(rf"^Accepted (?P<method>\S+) for (?P<user>\S+) from (?P<ip>{_IP}){_PORT}")
_INVALID_USER = re.compile(rf"^Invalid user (?P<user>\S+) from (?P<ip>{_IP}){_PORT}")
_NOT_ALLOWED = re.compile(rf"^User (?P<user>\S+) from (?P<ip>{_IP}) not allowed because")
_REFUSED = re.compile(rf"^refused connect from \S+ \((?P<ip>{_IP})\)")
_PAM_FAIL = re.compile(r"^pam_\w+\([^)]*\): authentication failure;")
_PAM_RHOST = re.compile(rf"\brhost=(?P<ip>{_IP})")
_PAM_USER = re.compile(r"\buser=(?P<user>\S+)")


class LinuxAuthParser(BaseParser):
    source_type = "linux_auth"

    def __init__(self, reference_time: datetime | None = None) -> None:
        # Only used to infer the missing year; injectable so tests are deterministic.
        self._reference_time = reference_time

    def parse(self, raw_log: str | Mapping[str, Any]) -> ParsedEvent:
        line = require_text(raw_log, "Linux auth log")
        match = _SYSLOG.match(line)
        if not match:
            raise ParseError("invalid_log", "Line is not in syslog format (expected 'Mon DD HH:MM:SS host process[pid]: message')")

        timestamp, ts_metadata = self._timestamp(match)
        status, fields, extra = self._classify(match["msg"])

        metadata: dict[str, Any] = {"hostname": match["host"], "process": match["proc"], **ts_metadata, **extra}
        if match["pid"]:
            metadata["pid"] = int(match["pid"])
        if fields.get("port"):
            metadata["source_port"] = int(fields["port"])

        return {
            "timestamp": timestamp,
            "source": self.source_type,
            "event_type": "authentication",
            "action": "login",
            "status": status,
            "username": fields.get("user"),
            "source_ip": fields.get("ip"),
            "message": clip_message(match["msg"]),
            "metadata": metadata,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _classify(message: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Return (status, captured fields, extra metadata) or raise for unsupported messages."""
        if m := _FAILED.match(message):
            extra = {"auth_method": m["method"]}
            if m["invalid"]:
                extra["reason"] = "invalid_user"
            return "failed", m.groupdict(), extra
        if m := _ACCEPTED.match(message):
            return "success", m.groupdict(), {"auth_method": m["method"]}
        if m := _INVALID_USER.match(message):
            return "failed", m.groupdict(), {"reason": "invalid_user"}
        if m := _NOT_ALLOWED.match(message):
            return "blocked", m.groupdict(), {"reason": "user_not_allowed"}
        if m := _REFUSED.match(message):
            return "blocked", m.groupdict(), {"reason": "connection_refused"}
        if _PAM_FAIL.match(message):
            ip, user = _PAM_RHOST.search(message), _PAM_USER.search(message)
            return "failed", {"ip": ip["ip"] if ip else None, "user": user["user"] if user else None}, {"reason": "pam_authentication_failure"}
        raise ParseError("unsupported_event", "Syslog line is valid but is not a supported authentication message")

    def _timestamp(self, match: re.Match) -> tuple[Any, dict[str, Any]]:
        if match["mon"] is None:  # RFC 3339
            try:
                parsed = datetime.fromisoformat(match["ts"].replace("Z", "+00:00"))
            except ValueError:
                raise ParseError("invalid_field", "Timestamp is not a valid ISO 8601 date-time", "timestamp") from None
            if parsed.tzinfo is None:
                raise ParseError("invalid_field", "Timestamp has no time zone", "timestamp")
            return parsed.astimezone(timezone.utc), {}

        month = _MONTHS.get(match["mon"])
        if month is None:
            raise ParseError("invalid_field", "Unknown month in timestamp", "timestamp")
        hour, minute, second = (int(part) for part in match["time"].split(":"))
        reference = self._reference_time or datetime.now(timezone.utc)
        try:
            candidate = datetime(reference.year, month, int(match["day"]), hour, minute, second, tzinfo=timezone.utc)
            if candidate > reference + timedelta(days=1):  # e.g. a December line read in January
                candidate = candidate.replace(year=reference.year - 1)
        except ValueError:
            raise ParseError("invalid_field", "Timestamp is not a valid date/time", "timestamp") from None
        return candidate, {"timestamp_year_assumed": True, "timezone_assumed": "UTC"}
