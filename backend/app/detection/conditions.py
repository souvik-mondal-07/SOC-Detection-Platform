"""Rule conditions: a small, closed vocabulary interpreted by our own code.

Rules come from MongoDB and are treated as untrusted configuration. They are
validated into these models (unknown keys are rejected) and then interpreted
here. Nothing is ever evaluated as Python.

Supported keys (all optional unless noted):
  event_type, status, action, source   exact match on the event field
  username_present, source_ip_present  require the field to be present
  metadata                             {key: value | [values]} exact / any-of on event.metadata
  threshold + window_minutes           N matching events within the window (stateful)
  distinct_field                       count distinct values of a field instead of events (with threshold)
  correlation_field                    group by "source_ip" (default) or "username" (stateful rules)
  preceded_by                          {<same filters>, min_count} events that must come before
                                       the triggering event within window_minutes (sequence rule)
"""

import re
from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, ValidationError, field_validator, model_validator

from app.core.errors import summarize_validation_errors
from app.detection.base import InvalidRuleError
from app.models.common import SNAKE_CASE_PATTERN
from app.models.event import EventStatus, EventType, SecurityEvent

MAX_THRESHOLD = 1000
MAX_WINDOW_MINUTES = 1440  # 24 hours
MAX_METADATA_FILTERS = 10
MAX_METADATA_LIST = 20
MAX_METADATA_STRING = 200
DEFAULT_CORRELATION_FIELD = "source_ip"

METADATA_KEY_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
_METADATA_KEY = re.compile(METADATA_KEY_PATTERN)
_DISTINCT_FIELD = re.compile(r"^(username|source_ip|metadata\.[A-Za-z][A-Za-z0-9_]{0,63})$")

Scalar = StrictStr | StrictInt | StrictBool
CorrelationField = Literal["source_ip", "username"]

_STATUS_WORDS = {"failed": "failed", "success": "successful", "blocked": "blocked", "unknown": "unknown-status"}
_CORRELATION_LABELS = {"source_ip": "source IP", "username": "username"}


class RuleKind(str, Enum):
    STATELESS = "stateless"  # one event is enough
    THRESHOLD = "threshold"  # N matching events in a window
    DISTINCT = "distinct"  # N distinct values in a window
    SEQUENCE = "sequence"  # earlier events, then the triggering event


def _value(item: Any) -> Any:
    return item.value if isinstance(item, Enum) else item


def _same(left: Any, right: Any) -> bool:
    """Equality that, like MongoDB, does not treat True == 1 or "404" == 404."""
    return type(left) is type(right) and left == right


class EventFilters(BaseModel):
    """Field filters shared by a rule and its `preceded_by` stage."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_type: EventType | None = None
    status: EventStatus | None = None
    action: str | None = Field(default=None, pattern=SNAKE_CASE_PATTERN)
    source: str | None = Field(default=None, pattern=SNAKE_CASE_PATTERN)
    username_present: StrictBool = False
    source_ip_present: StrictBool = False
    metadata: dict[str, Scalar | list[Scalar]] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _metadata_is_simple(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_METADATA_FILTERS:
            raise ValueError(f"at most {MAX_METADATA_FILTERS} metadata filters are allowed")
        for key, item in value.items():
            if not _METADATA_KEY.match(key):
                raise ValueError("metadata filter keys must be simple identifiers (letters, digits, underscore)")
            items = item if isinstance(item, list) else [item]
            if not items or len(items) > MAX_METADATA_LIST:
                raise ValueError(f"metadata filter lists need 1 to {MAX_METADATA_LIST} values")
            if any(isinstance(v, str) and len(v) > MAX_METADATA_STRING for v in items):
                raise ValueError(f"metadata filter strings are limited to {MAX_METADATA_STRING} characters")
        return value

    def has_criteria(self) -> bool:
        return any((self.event_type, self.status, self.action, self.source,
                    self.username_present, self.source_ip_present, self.metadata))

    def matches(self, event: SecurityEvent) -> bool:
        """True if this single event satisfies every filter. Missing fields never match a filter."""
        for name in ("event_type", "status", "action", "source"):
            expected = getattr(self, name)
            if expected is not None and _value(getattr(event, name)) != _value(expected):
                return False
        if self.username_present and not event.username:
            return False
        if self.source_ip_present and not event.source_ip:
            return False
        for key, expected in self.metadata.items():
            actual = event.metadata.get(key)
            options = expected if isinstance(expected, list) else [expected]
            if not any(_same(actual, option) for option in options):
                return False
        return True

    def query_filters(self) -> dict[str, Any]:
        """Keyword filters for EventStore queries (only the fields that are set)."""
        filters: dict[str, Any] = {}
        for name in ("event_type", "status", "action", "source"):
            if getattr(self, name) is not None:
                filters[name] = _value(getattr(self, name))
        if self.username_present:
            filters["username_present"] = True
        if self.source_ip_present:
            filters["source_ip_present"] = True
        if self.metadata:
            filters["metadata"] = dict(self.metadata)
        return filters

    def describe(self, noun: str = "events") -> str:
        """Plain-language description, e.g. 'failed authentication events (http_status in [403, 404])'."""
        words = []
        if self.status is not None:
            words.append(_STATUS_WORDS.get(_value(self.status), _value(self.status)))
        if self.event_type is not None:
            words.append(_value(self.event_type))
        text = " ".join([*words, noun])
        extras = []
        if self.action:
            extras.append(f"action={self.action}")
        if self.source:
            extras.append(f"source={self.source}")
        for key, expected in self.metadata.items():
            extras.append(f"{key} in {expected}" if isinstance(expected, list) else f"{key}={expected}")
        return f"{text} ({', '.join(extras)})" if extras else text


class PrecedingEvents(EventFilters):
    """Events that must occur before the triggering event (sequence rules)."""

    min_count: StrictInt = Field(ge=1, le=MAX_THRESHOLD)


class RuleConditions(EventFilters):
    threshold: StrictInt | None = Field(default=None, ge=1, le=MAX_THRESHOLD)
    window_minutes: StrictInt | None = Field(default=None, ge=1, le=MAX_WINDOW_MINUTES)
    distinct_field: str | None = None
    correlation_field: CorrelationField | None = None
    preceded_by: PrecedingEvents | None = None

    @field_validator("distinct_field")
    @classmethod
    def _distinct_field_allowed(cls, value: str | None) -> str | None:
        if value is not None and not _DISTINCT_FIELD.match(value):
            raise ValueError("distinct_field must be 'username', 'source_ip' or 'metadata.<key>'")
        return value

    @model_validator(mode="after")
    def _check_combination(self) -> Self:
        if not self.has_criteria():
            raise ValueError("a rule needs at least one filter (for example event_type); otherwise it would match every event")
        if self.preceded_by is not None:
            if self.threshold is not None or self.distinct_field is not None:
                raise ValueError("preceded_by cannot be combined with threshold or distinct_field")
            if self.window_minutes is None:
                raise ValueError("preceded_by requires window_minutes")
            if not self.preceded_by.has_criteria():
                raise ValueError("preceded_by needs at least one filter")
        elif self.threshold is not None:
            if self.window_minutes is None:
                raise ValueError("threshold requires window_minutes")
        else:
            if self.distinct_field is not None:
                raise ValueError("distinct_field requires threshold")
            if self.window_minutes is not None:
                raise ValueError("window_minutes requires threshold or preceded_by")
            if self.correlation_field is not None:
                raise ValueError("correlation_field only applies to threshold or sequence rules")
        if self.kind is not RuleKind.STATELESS and self.correlation_field is None:
            # Never count events globally: group by source IP unless the rule says otherwise.
            self.correlation_field = DEFAULT_CORRELATION_FIELD
        return self

    @property
    def kind(self) -> RuleKind:
        if self.preceded_by is not None:
            return RuleKind.SEQUENCE
        if self.threshold is not None:
            return RuleKind.DISTINCT if self.distinct_field else RuleKind.THRESHOLD
        return RuleKind.STATELESS

    @property
    def correlation_label(self) -> str:
        return _CORRELATION_LABELS.get(self.correlation_field or "", "")


def parse_conditions(raw: Mapping[str, Any]) -> RuleConditions:
    """Validate stored rule conditions. Raises InvalidRuleError (field names only, no values)."""
    try:
        return RuleConditions.model_validate(dict(raw))
    except ValidationError as exc:
        problems = "; ".join(f"{item['field']}: {item['message']}" for item in summarize_validation_errors(exc.errors()))
        raise InvalidRuleError(f"Invalid rule conditions ({problems})") from None


def field_value(event: SecurityEvent, field: str) -> str | int | bool | None:
    """Read a correlation / distinct field from an event. Missing or non-scalar values give None."""
    if field == "source_ip":
        return event.source_ip
    if field == "username":
        return event.username
    if field.startswith("metadata."):
        value = event.metadata.get(field[len("metadata."):])
        return value if isinstance(value, (str, int, bool)) else None
    return None
