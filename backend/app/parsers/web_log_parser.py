"""Web access logs in Common Log Format (an optional Combined-format referer and
user agent are also accepted):

  192.168.1.20 - - [02/Oct/2026:10:20:10 +0000] "GET /admin HTTP/1.1" 404 512

Parsing only describes the request. A 404 is recorded as status "failed" because
the request did not succeed; it is not judged suspicious. That is for detection rules.
"""

import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.parsers.base import BaseParser, ParsedEvent, ParseError, clip_message, require_text

_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}

_LINE = re.compile(
    r'^(?P<ip>[0-9A-Fa-f:.]+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d{3}) (?P<size>\d+|-)'
    r'(?: "(?P<referer>[^"]*)" "(?P<agent>[^"]*)")?\s*$'
)
_TS = re.compile(r"^(\d{2})/([A-Z][a-z]{2})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})$")
_REQUEST = re.compile(r"^(?P<method>[A-Z]{3,10}) (?P<path>\S+)(?: (?P<protocol>HTTP/\d(?:\.\d)?))?$")
_MAX_PATH = 500
_MAX_AGENT = 300


class WebLogParser(BaseParser):
    source_type = "web_application"

    def parse(self, raw_log: str | Mapping[str, Any]) -> ParsedEvent:
        line = require_text(raw_log, "web access log")
        match = _LINE.match(line)
        if not match:
            raise ParseError("invalid_log", "Line is not in Common Log Format")
        request = _REQUEST.match(match["request"])
        if not request:
            raise ParseError("invalid_field", "Request line is not 'METHOD /path [HTTP/x]'", "request")

        http_status = int(match["status"])
        if not 100 <= http_status <= 599:
            raise ParseError("invalid_field", "HTTP status must be between 100 and 599", "http_status")

        metadata: dict[str, Any] = {
            "method": request["method"],
            "path": request["path"][:_MAX_PATH],
            "http_status": http_status,
        }
        if request["protocol"]:
            metadata["protocol"] = request["protocol"]
        if match["size"] != "-":
            metadata["response_size"] = int(match["size"])
        if match["agent"] and match["agent"] != "-":
            metadata["user_agent"] = match["agent"][:_MAX_AGENT]

        message = f'{request["method"]} {request["path"]}'
        if request["protocol"]:
            message += f' {request["protocol"]}'
        message += f" {http_status}"

        return {
            "timestamp": self._timestamp(match["ts"]),
            "source": self.source_type,
            "event_type": "web",
            "action": "http_request",
            "status": "failed" if http_status >= 400 else "success",
            "source_ip": match["ip"],
            "message": clip_message(message),
            "metadata": metadata,
        }

    @staticmethod
    def _timestamp(value: str) -> datetime:
        m = _TS.match(value)
        month = _MONTHS.get(m[2]) if m else None
        if not m or month is None:
            raise ParseError("invalid_field", "Timestamp is not in 'DD/Mon/YYYY:HH:MM:SS +ZZZZ' form", "timestamp")
        offset = timedelta(hours=int(m[8]), minutes=int(m[9]))
        try:
            local = datetime(int(m[3]), month, int(m[1]), int(m[4]), int(m[5]), int(m[6]),
                             tzinfo=timezone(offset if m[7] == "+" else -offset))
        except ValueError:
            raise ParseError("invalid_field", "Timestamp is not a valid date/time", "timestamp") from None
        return local.astimezone(timezone.utc)
