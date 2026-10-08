import pytest
from pydantic import ValidationError

from app.models.alert import Alert, AlertStatus


def build(**kw):
    data = dict(alert_id="ALT-20261007-000001", rule_id="AUTH-001", title="t", description="d", severity="high", event_ids=["evt_1"])
    return Alert(**{**data, **kw})


def test_defaults_open_and_utc():
    alert = build()
    assert alert.status == "open" and alert.source_ip is None
    assert alert.created_at.utcoffset().total_seconds() == 0


def test_future_statuses_remain_valid():
    assert {s.value for s in AlertStatus} >= {"open", "investigating", "resolved", "false_positive"}


@pytest.mark.parametrize("kw", [{"severity": "urgent"}, {"event_ids": []}, {"source_ip": "not-an-ip"}, {"event_ids": ["a", "a"]}, {"extra": 1}])
def test_invalid_rejected(kw):
    with pytest.raises(ValidationError):
        build(**kw)
