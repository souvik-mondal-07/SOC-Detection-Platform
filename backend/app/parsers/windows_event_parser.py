"""Simplified Windows Event JSON (not the full Windows Event Log schema).

Mapped event IDs: 4624 (successful logon) and 4625 (failed logon). Other IDs are
rejected as unsupported. Add an entry to SUPPORTED_EVENTS to support more.

Fields read: EventID (required), TimeCreated, Computer, TargetUserName,
IpAddress, Message, LogonType. Missing optional fields are left out, not invented.
"""

from collections.abc import Mapping
from typing import Any

from app.parsers.base import BaseParser, ParsedEvent, ParseError, clip_message, present, require_mapping

# event id -> (action, status, description used when the event has no Message)
SUPPORTED_EVENTS: dict[int, tuple[str, str, str]] = {
    4624: ("login", "success", "An account was successfully logged on."),
    4625: ("login", "failed", "An account failed to log on."),
}


class WindowsEventParser(BaseParser):
    source_type = "windows_event"

    def parse(self, raw_log: str | Mapping[str, Any]) -> ParsedEvent:
        record = require_mapping(raw_log, "Windows event")

        raw_id = record.get("EventID")
        if raw_id is None or isinstance(raw_id, bool):
            raise ParseError("missing_field", "EventID is required", "EventID")
        try:
            event_id = int(raw_id)
        except (TypeError, ValueError):
            raise ParseError("invalid_field", "EventID must be a number", "EventID") from None
        if event_id not in SUPPORTED_EVENTS:
            raise ParseError("unsupported_event", f"Event ID {event_id} is not supported (supported: {', '.join(map(str, SUPPORTED_EVENTS))})", "EventID")
        action, status, description = SUPPORTED_EVENTS[event_id]

        metadata: dict[str, Any] = {"event_id": event_id}
        if computer := present(record.get("Computer")):
            metadata["computer"] = str(computer)
        if (logon_type := present(record.get("LogonType"))) is not None:
            metadata["logon_type"] = logon_type

        message = present(record.get("Message"))
        return {
            "timestamp": present(record.get("TimeCreated")),  # missing -> stamped at ingestion and flagged
            "source": self.source_type,
            "event_type": "authentication",
            "action": action,
            "status": status,
            "username": present(record.get("TargetUserName")),
            "source_ip": present(record.get("IpAddress")),
            "message": clip_message(str(message)) if message is not None else description,
            "metadata": metadata,
        }
