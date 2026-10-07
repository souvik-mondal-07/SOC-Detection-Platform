"""Field-level normalization rules for security events.

Pure functions with no I/O. They are attached to the schemas in event.py as
"before" validators, so every entry point (the API now, log parsers later)
applies exactly the same rules. They only canonicalise text; they never decide
whether a value is allowed. Unknown values pass through unchanged and are then
rejected by the schema. See docs/architecture/event-normalization.md.
"""

import re
from datetime import datetime
from typing import Any

_SEPARATORS = re.compile(r"[\s\-]+")
_ISO_DATETIME_START = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}")

# Small, explicit alias tables. Anything not listed is left alone.
SOURCE_ALIASES = {"windows": "windows_event", "web": "web_application", "app": "application"}
EVENT_TYPE_ALIASES = {
    "auth": "authentication",
    "priv": "privilege",
    "net": "network",
    "sys": "system",
    "app": "application",
}
STATUS_ALIASES = {
    "failure": "failed",
    "fail": "failed",
    "succeeded": "success",
    "successful": "success",
    "block": "blocked",
    "n/a": "unknown",
    "na": "unknown",
    "none": "unknown",
}


def blank_to_none(value: Any) -> Any:
    """Whitespace-only strings count as 'not provided'."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _canonical(value: Any) -> Any:
    """Trim, lowercase, and turn spaces/hyphens into underscores. Non-strings are returned as-is."""
    value = blank_to_none(value)
    if isinstance(value, str):
        return _SEPARATORS.sub("_", value.strip().lower())
    return value


def _with_aliases(value: Any, aliases: dict[str, str]) -> Any:
    value = _canonical(value)
    return aliases.get(value, value) if isinstance(value, str) else value


def normalize_source(value: Any) -> Any:
    return _with_aliases(value, SOURCE_ALIASES)


def normalize_event_type(value: Any) -> Any:
    return _with_aliases(value, EVENT_TYPE_ALIASES)


def normalize_status(value: Any) -> Any:
    return _with_aliases(value, STATUS_ALIASES)


def normalize_status_or_unknown(value: Any) -> Any:
    """For incoming events: a missing, null or blank status is the neutral value 'unknown'."""
    normalized = normalize_status(value)
    return "unknown" if normalized is None else normalized


def normalize_action(value: Any) -> Any:
    return _canonical(value)


def prepare_timestamp(value: Any) -> Any:
    """Accept only ISO 8601 date-time strings (or datetime objects from code).

    Pydantic alone would also accept epoch numbers and digit-only strings, which
    are ambiguous (seconds vs milliseconds), so they are rejected here.
    """
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str) and _ISO_DATETIME_START.match(value.strip()):
        return value.strip()
    raise ValueError("timestamp must be an ISO 8601 date-time with a timezone, e.g. 2026-10-02T10:15:23Z")
