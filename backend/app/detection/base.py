"""Shared contracts for the detection package."""

from typing import Any, Protocol

from app.models.event import SecurityEvent


class InvalidRuleError(Exception):
    """A stored rule has conditions the engine does not understand.

    The message names the offending fields only, never the stored values.
    """


class EventStore(Protocol):
    """What stateful rules need from event storage.

    EventRepository satisfies this. Both methods take the same keyword filters
    (event_type, status, action, source, username, source_ip, username_present,
    source_ip_present, metadata, start, end); `start` / `end` are inclusive.
    """

    def count_matching_events(self, **criteria: Any) -> int: ...

    def find_matching_events(self, *, limit: int = ..., **criteria: Any) -> list[SecurityEvent]: ...
