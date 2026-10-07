"""Common parser interface.

A parser turns ONE raw log record into a dict of EventCreate fields
("parsed event data"). It does not validate against the event schema, touch the
database or decide whether anything is suspicious: validation/normalization is
done by EventCreate and storage by the ingestion service (see parsing_service.py).

To add a format: subclass BaseParser, set `source_type` to a SourceType value and
register it in registry.py. Existing parsers stay untouched. Parsers must be
stateless because the registry shares one instance per source type.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

ParsedEvent = dict[str, Any]

MAX_MESSAGE_CHARS = 1000  # same limit as the stored event's `message`


class ParseError(Exception):
    """A raw log could not be turned into an event.

    Messages describe the problem but never include the raw log, which may
    contain sensitive data.
    """

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class BaseParser(ABC):
    source_type: ClassVar[str]

    @abstractmethod
    def parse(self, raw_log: str | Mapping[str, Any]) -> ParsedEvent:
        """Return EventCreate-compatible fields or raise ParseError."""


# ---------------------------------------------------------------- shared helpers

def require_text(raw_log: Any, what: str) -> str:
    if not isinstance(raw_log, str) or not raw_log.strip():
        raise ParseError("invalid_log", f"Expected a non-empty {what} line")
    return raw_log.strip()


def require_mapping(raw_log: Any, what: str) -> dict[str, Any]:
    """Accept a JSON object or a string containing one."""
    if isinstance(raw_log, str):
        try:
            raw_log = json.loads(raw_log)
        except ValueError:
            raise ParseError("invalid_log", f"Input is not valid JSON ({what} expected)") from None
    if not isinstance(raw_log, Mapping):
        raise ParseError("invalid_log", f"Expected a JSON object ({what})")
    return dict(raw_log)


def clip_message(message: str) -> str:
    return message if len(message) <= MAX_MESSAGE_CHARS else message[: MAX_MESSAGE_CHARS - 3] + "..."


def present(value: Any) -> Any:
    """None for missing/blank/placeholder ('-') values, so nothing is invented or stored as noise."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "-"):
        return None
    return value
