r"""Create or update the initial detection rules in MongoDB.

Run manually from the backend folder (never runs automatically, not on app startup):
    python ..\scripts\seed_detection_rules.py

- Safe to run repeatedly: a rule is matched by rule_id and updated, never duplicated.
- Definition fields (name, category, description, severity, conditions) are refreshed.
  The `enabled` flag and `created_at` of an existing rule are kept, so a rule an
  operator disabled stays disabled.
- Never deletes anything.
- Only touches the detection_rules collection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pymongo.database import Database  # noqa: E402

from app.core.database import check_connection, close_client, get_database  # noqa: E402
from app.core.errors import DatabaseUnavailableError  # noqa: E402
from app.detection.conditions import parse_conditions  # noqa: E402
from app.models.rule import DetectionRule  # noqa: E402
from app.repositories.detection_rule_repository import DetectionRuleRepository  # noqa: E402
from app.repositories.initialization import initialize_database  # noqa: E402

SUSPICION_NOTE = "This indicates suspicious activity that requires investigation; it is not proof of an attack."


def build_rules() -> list[DetectionRule]:
    return [
        DetectionRule(
            rule_id="AUTH-001", name="Multiple Failed Logins", category="authentication", severity="high",
            description="Detect repeated failed authentication attempts: 5 failed authentication events "
                        "from the same source IP within 5 minutes. " + SUSPICION_NOTE,
            conditions={"event_type": "authentication", "status": "failed",
                        "threshold": 5, "window_minutes": 5, "correlation_field": "source_ip"},
        ),
        DetectionRule(
            rule_id="AUTH-002", name="Invalid User Login Attempt", category="authentication", severity="medium",
            description="Detect a failed login for an account that does not exist, as reported by the log parser "
                        "(metadata.reason = invalid_user). " + SUSPICION_NOTE,
            conditions={"event_type": "authentication", "status": "failed", "action": "login",
                        "metadata": {"reason": "invalid_user"}},
        ),
        DetectionRule(
            rule_id="AUTH-003", name="Successful Login After Failed Attempts", category="authentication", severity="high",
            description="Detect a successful login from a source IP that had 3 or more failed logins in the previous "
                        "10 minutes. Possible credential guessing that succeeded. " + SUSPICION_NOTE,
            conditions={"event_type": "authentication", "status": "success", "action": "login",
                        "window_minutes": 10, "correlation_field": "source_ip",
                        "preceded_by": {"event_type": "authentication", "status": "failed", "action": "login", "min_count": 3}},
        ),
        DetectionRule(
            rule_id="WEB-001", name="Excessive HTTP Errors", category="web", severity="medium",
            description="Detect 10 HTTP 403/404 responses to the same source IP within 5 minutes. "
                        "Possible probing for hidden resources. " + SUSPICION_NOTE,
            conditions={"event_type": "web", "metadata": {"http_status": [403, 404]},
                        "threshold": 10, "window_minutes": 5, "correlation_field": "source_ip"},
        ),
        DetectionRule(
            rule_id="NET-001", name="Multiple Destination Ports", category="network", severity="medium",
            description="Detect one source IP connecting to 10 or more distinct destination ports within 5 minutes. "
                        "A scan-like behavior indicator, not a confirmed port scan. " + SUSPICION_NOTE,
            conditions={"event_type": "network", "distinct_field": "metadata.destination_port",
                        "threshold": 10, "window_minutes": 5, "correlation_field": "source_ip"},
        ),
    ]


def seed(database: Database) -> dict[str, str]:
    """Create or update the rules. Returns {rule_id: 'created' | 'updated'}."""
    initialize_database(database)
    repository = DetectionRuleRepository(database)
    outcome = {}
    for rule in build_rules():
        parse_conditions(rule.conditions)  # a seed rule the engine cannot interpret is a bug: fail loudly
        _, created = repository.save_rule(rule)
        outcome[rule.rule_id] = "created" if created else "updated"
    return outcome


def main() -> int:
    database = get_database()
    try:
        if not check_connection(database):
            print("Cannot reach MongoDB. Start it and check MONGODB_URI in backend/.env.", file=sys.stderr)
            return 1
        outcome = seed(database)
    except DatabaseUnavailableError:
        print("Lost connection to MongoDB while seeding.", file=sys.stderr)
        return 1
    finally:
        close_client()
    for rule_id, action in outcome.items():
        print(f"{rule_id}: {action}")
    print(f"{len(outcome)} detection rules ensured in 'detection_rules'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
