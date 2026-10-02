r"""Insert a small set of SYNTHETIC development records into MongoDB.

Run manually from the backend folder (never runs automatically):
    python ..\scripts\seed_database.py

- Safe to run repeatedly: records whose ID already exists are skipped.
- Never deletes or overwrites anything.
- Refuses to run when ENVIRONMENT=production.
- All values are fictional (test_user, demo_user, 192.168.1.x). No real data.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pymongo.database import Database  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import check_connection, close_client, get_database  # noqa: E402
from app.core.errors import DatabaseUnavailableError  # noqa: E402
from app.models.alert import Alert  # noqa: E402
from app.models.common import MongoModel  # noqa: E402
from app.models.event import SecurityEvent  # noqa: E402
from app.models.rule import DetectionRule  # noqa: E402
from app.repositories.alert_repository import AlertRepository  # noqa: E402
from app.repositories.base import BaseRepository, DuplicateRecordError  # noqa: E402
from app.repositories.detection_rule_repository import DetectionRuleRepository  # noqa: E402
from app.repositories.event_repository import EventRepository  # noqa: E402
from app.repositories.initialization import initialize_database  # noqa: E402

TAG = "[Synthetic seed]"
UTC = timezone.utc


def _t(hour: int, minute: int, second: int) -> datetime:
    return datetime(2026, 10, 2, hour, minute, second, tzinfo=UTC)


def build_events() -> list[SecurityEvent]:
    meta = {"synthetic": True, "seed": "step3"}

    def event(n: int, when: datetime, **kw) -> SecurityEvent:
        return SecurityEvent(event_id=f"evt_{n:03d}", timestamp=when, metadata=dict(meta), **kw)

    failed = dict(source="linux_auth", event_type="authentication", action="login", status="failed",
                  username="test_user", source_ip="192.168.1.20", message="Failed password for test_user")
    return [
        event(1, _t(10, 15, 23), **failed),
        event(2, _t(10, 15, 31), **failed),
        event(3, _t(10, 15, 39), **failed),
        event(4, _t(10, 15, 47), **failed),
        event(5, _t(10, 15, 55), **failed),
        event(6, _t(10, 16, 10), source="linux_auth", event_type="authentication", action="login",
              status="success", username="test_user", source_ip="192.168.1.20",
              message="Accepted login for test_user"),
        event(7, _t(10, 5, 2), source="linux_auth", event_type="authentication", action="login",
              status="success", username="demo_user", source_ip="192.168.1.30",
              message="Accepted login for demo_user"),
        event(8, _t(10, 18, 40), source="audit_log", event_type="privilege", action="privilege_change",
              status="success", username="test_user", source_ip="192.168.1.20",
              message="Synthetic privilege change: demo_user added to group admins"),
    ]


def build_rules() -> list[DetectionRule]:
    return [
        DetectionRule(
            rule_id="AUTH-001", name="Multiple Failed Logins", category="authentication", severity="high",
            description=f"{TAG} Detect repeated failed authentication attempts",
            conditions={"event_type": "authentication", "status": "failed", "threshold": 5, "window_minutes": 5},
        ),
        DetectionRule(
            rule_id="PRIV-001", name="Privilege Change Activity", category="privilege", severity="medium",
            description=f"{TAG} Detect privilege-change events",
            conditions={"event_type": "privilege", "action": "privilege_change"},
        ),
        DetectionRule(
            rule_id="AUTH-002", name="Successful Login After Repeated Failures", category="authentication",
            severity="critical",
            description=f"{TAG} Illustrates that conditions can hold richer structures such as ordered stages",
            conditions={"window_minutes": 10, "stages": [
                {"event_type": "authentication", "status": "failed", "min_count": 5},
                {"event_type": "authentication", "status": "success", "min_count": 1},
            ]},
        ),
    ]


def build_alerts() -> list[Alert]:
    return [
        Alert(alert_id="alert_001", rule_id="AUTH-001", title="Multiple Failed Logins", severity="high",
              description=f"{TAG} 5 failed logins for test_user from 192.168.1.20",
              source_ip="192.168.1.20", event_ids=[f"evt_{n:03d}" for n in range(1, 6)],
              created_at=_t(10, 20, 0), updated_at=_t(10, 20, 0)),
        Alert(alert_id="alert_002", rule_id="AUTH-002", title="Successful Login After Repeated Failures",
              severity="critical", status="investigating",
              description=f"{TAG} Successful login for test_user after 5 failures",
              source_ip="192.168.1.20", event_ids=[f"evt_{n:03d}" for n in range(1, 7)],
              created_at=_t(10, 21, 0), updated_at=_t(10, 22, 0)),
    ]


def _insert_all(repository: BaseRepository, items: list[MongoModel]) -> tuple[int, int]:
    inserted = skipped = 0
    for item in items:
        try:
            repository.create(item)
            inserted += 1
        except DuplicateRecordError:
            skipped += 1
    return inserted, skipped


def seed(database: Database) -> dict[str, tuple[int, int]]:
    """Insert seed records; returns {collection: (inserted, skipped)}."""
    initialize_database(database)
    plan = [
        (EventRepository(database), build_events()),
        (DetectionRuleRepository(database), build_rules()),
        (AlertRepository(database), build_alerts()),
    ]
    return {repo.collection_name: _insert_all(repo, items) for repo, items in plan}


def main() -> int:
    if get_settings().environment.lower() == "production":
        print("Refusing to seed: ENVIRONMENT is 'production'.", file=sys.stderr)
        return 1
    database = get_database()
    try:
        if not check_connection(database):
            print("Cannot reach MongoDB. Start it and check MONGODB_URI in backend/.env.", file=sys.stderr)
            return 1
        summary = seed(database)
    except DatabaseUnavailableError:
        print("Lost connection to MongoDB while seeding.", file=sys.stderr)
        return 1
    finally:
        close_client()
    print("Synthetic seed data (nothing was deleted or overwritten):")
    for collection, (inserted, skipped) in summary.items():
        print(f"  {collection}: {inserted} inserted, {skipped} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
