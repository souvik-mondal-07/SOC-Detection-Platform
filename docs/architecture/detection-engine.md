# Detection Engine (Step 6)

## Purpose

The detection engine answers one question: **did this stored security event match a detection rule?** It reads normalized events and rules from MongoDB and returns a structured `DetectionResult` per rule. It does not create alerts, notify anyone or change any data. Alert generation is Step 8.

```text
Security Events (MongoDB)
        |
        v
Detection Service      loads the event and the enabled rules
        |
        v
Detection Engine       one result per enabled rule
        |
        v
Rule Evaluator         conditions, thresholds, windows, correlation
        |
        v
Detection Results      returned to the caller, not stored
```

Detection is deliberately **not** part of parsing or ingestion. It is called explicitly through the service or the API; automatic detection after ingestion is a later step.

## Code layout

| File | Responsibility |
| --- | --- |
| `app/detection/conditions.py` | Closed vocabulary of rule conditions, validation, single-event matching |
| `app/detection/rule_evaluator.py` | Evaluates one rule for one event (stateless, threshold, distinct, sequence) |
| `app/detection/engine.py` | Runs all enabled rules, skips disabled and invalid ones |
| `app/detection/result.py` | `DetectionResult`, `EventDetection`, `BatchDetection` |
| `app/detection/base.py` | `InvalidRuleError` and the `EventStore` interface the evaluator needs |
| `app/services/detection_service.py` | Loads events and rules through the repositories; no HTTP code |
| `app/api/v1/detection.py` | Two POST endpoints |
| `scripts/seed_detection_rules.py` | Manual rule seeding |

The detection package never touches a MongoDB collection. It talks to `EventRepository` (through the `EventStore` interface) and `DetectionRuleRepository`.

## Rules are data

Rules are documents in `detection_rules` using the Step 3 model. No rule ID is hard-coded in Python; behaviour comes only from `conditions`:

```json
{
  "rule_id": "AUTH-001",
  "name": "Multiple Failed Logins",
  "category": "authentication",
  "severity": "high",
  "enabled": true,
  "conditions": {
    "event_type": "authentication",
    "status": "failed",
    "threshold": 5,
    "window_minutes": 5,
    "correlation_field": "source_ip"
  }
}
```

### Condition keys

| Key | Meaning |
| --- | --- |
| `event_type`, `status`, `action`, `source` | Exact match on the event field (same values as normalization produces) |
| `username_present`, `source_ip_present` | The event must carry that field |
| `metadata` | `{key: value}` for equality or `{key: [v1, v2]}` for any-of, on `event.metadata` (for example `{"http_status": [403, 404]}`) |
| `threshold` + `window_minutes` | Stateful: at least N matching events within the window |
| `distinct_field` | With `threshold`: count distinct values of `username`, `source_ip` or `metadata.<key>` instead of events |
| `correlation_field` | Group by `source_ip` (default) or `username` |
| `preceded_by` | Sequence: `{<filters>, "min_count": N}` events that must come before the triggering event (needs `window_minutes`) |

A rule needs at least one filter, otherwise it would match every event.

## Stateless vs stateful rules

- **Stateless** (no `threshold`, no `preceded_by`): the event alone decides. `AUTH-002` is stateless.
- **Stateful**: the engine asks MongoDB for the other events it needs. There is no in-memory state, cache or external system (no Redis, Kafka or Celery); every evaluation re-reads the relevant slice of `security_events`.

### Thresholds and time windows

For a threshold rule the evaluated event must itself match the filters. The engine then looks for a window of `window_minutes` that **contains the evaluated event** and holds at least `threshold` matching events (or distinct values) from the same correlation value. Window edges are inclusive: exactly 5 minutes apart counts as within 5 minutes.

Because the window only has to contain the event, every event of a burst is reported as part of it, including the first, and re-evaluating old events later gives the same answer. A consequence is that events newer than the evaluated one can complete the window.

### Correlation

Stateful events are grouped by `correlation_field`, default `source_ip`. 5 failures from `192.168.1.20` and 2 from `192.168.1.50` are evaluated separately and never added together. An event that lacks the correlation field cannot be correlated and does not match (the result says so). A stateful rule without `correlation_field` uses `source_ip`, so the Step 3 sample `AUTH-001` keeps working.

### Sequences

For `preceded_by`, the **triggering event** is the one matching the top-level filters (a successful login for `AUTH-003`). The rule matches when at least `min_count` `preceded_by` events from the same correlation value happened in the `window_minutes` up to and including the trigger's timestamp. Evaluating one of the earlier failures does not match `AUTH-003`; evaluate the success event. This is a simple ordered pair of stages, not a general correlation framework.

## Detection results

```json
{
  "matched": true,
  "rule_id": "AUTH-001",
  "rule_name": "Multiple Failed Logins",
  "category": "authentication",
  "event_id": "evt_001",
  "reason": "5 failed authentication events from the same source IP within 5 minutes",
  "severity": "high",
  "matched_event_ids": ["evt_001", "evt_002", "evt_003", "evt_004", "evt_005"],
  "details": {"threshold": 5, "window_minutes": 5, "correlation_field": "source_ip", "correlation_value": "192.168.1.20", "observed": 5}
}
```

A non-match has `"matched": false`, no `severity`, and a reason such as `Event did not satisfy rule conditions` or `Threshold not reached: 4 matching event(s) within 5 minutes, 5 required`. `matched_event_ids` is capped at 100.

## Initial rules

Created by `python ..\scripts\seed_detection_rules.py` (from `backend`).

| Rule | Category | Severity | Logic |
| --- | --- | --- | --- |
| `AUTH-001` Multiple Failed Logins | authentication | high | 5 failed authentication events, same source IP, 5 min |
| `AUTH-002` Invalid User Login Attempt | authentication | medium | Failed login with `metadata.reason = invalid_user` (set by the Linux auth parser); the message text is not searched |
| `AUTH-003` Successful Login After Failed Attempts | authentication | high | Successful login preceded by 3 or more failed logins from the same IP within 10 min |
| `WEB-001` Excessive HTTP Errors | web | medium | 10 web events with `http_status` 403 or 404, same source IP, 5 min |
| `NET-001` Multiple Destination Ports | network | medium | 10 distinct `metadata.destination_port` values, same source IP, 5 min |

`WEB-001` and `NET-001` are indicators only. Many 404s can be a broken link checker, and many ports can be a monitoring tool; a match means the activity is suspicious and needs investigation. `NET-001` is scan-like behaviour, not a confirmed port scan. The rule descriptions say so.

**Seeding behaviour.** Rules are matched by `rule_id`, so running the script twice never duplicates. It refreshes name, category, description, severity and conditions, but keeps an existing rule's `enabled` flag and `created_at`, so a rule you disabled stays disabled. It never runs on application startup.

**Step 3 sample data.** `scripts/seed_database.py` created a sample `AUTH-002` ("Successful Login After Repeated Failures", with a `stages` condition). The engine does not understand `stages`, so until the Step 6 seed replaces that document, the engine skips it and lists it in `skipped_rule_ids`. Running `seed_detection_rules.py` replaces it in place. Running `seed_database.py` afterwards does not overwrite the new rule (it skips existing IDs), but it only inserts a missing `AUTH-002` using the old sample definition.

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/detection/evaluate/{event_id}` | Evaluate one stored event. Unknown event: `404`. |
| `POST /api/v1/detection/evaluate` | Body `{"event_ids": [...]}`, 1 to 500 IDs. Unknown IDs are listed in `not_found_event_ids`. |

```json
{
  "success": true,
  "event_id": "evt_001",
  "matches": [ { "matched": true, "rule_id": "AUTH-001", "severity": "high", "reason": "..." } ],
  "rules_evaluated": 5,
  "skipped_rule_ids": []
}
```

`matches` contains only rules that matched; no matches gives `[]`. The batch response adds `events_evaluated`, `total_matches` and one `{event_id, matches}` entry per evaluated event. Neither endpoint writes anything.

## Performance and indexes

Stateful rules never load the whole collection. Each evaluation does one indexed `count_documents`; only if the count could reach the threshold does it read the matching events, oldest first, capped at 5000 per rule evaluation. Two compound indexes were added to `security_events` (created by the normal database initialization):

| Index | Serves |
| --- | --- |
| `ix_detection_type_status_ip_timestamp` (`event_type`, `status`, `source_ip`, `timestamp`) | counts per source IP: `AUTH-001`, `AUTH-003`, `WEB-001`, `NET-001` |
| `ix_detection_type_status_user_timestamp` (`event_type`, `status`, `username`, `timestamp`) | rules correlated by username |

The existing `source_ip + timestamp` and `event_type + timestamp` indexes also help.

## Security considerations

- Rules from MongoDB are untrusted configuration. They are validated into closed models (unknown keys rejected), then interpreted by our own code. There is no `eval`, `exec`, dynamic import or user-supplied query operator; a test scans the detection code for them.
- Validated: severity and category (Step 3 model), condition keys, enum values, `threshold` 1 to 1000, `window_minutes` 1 to 1440, `correlation_field` (`source_ip` or `username`), `distinct_field`, metadata keys (simple identifiers) and metadata values (plain strings, numbers, booleans).
- The repository builds queries from fixed field names and plain values, so a stored rule cannot inject `$where` or other operators.
- A rule that fails validation is skipped and logged (rule ID only) and reported in `skipped_rule_ids`. A stored rule document that fails the rule model is skipped when rules are loaded. Neither stops other rules. Error messages never echo stored values.
- Disabled rules are never evaluated and cannot match.
- Database outages are not hidden: they return `503` as elsewhere.

## Current limitations

- Results are not stored and no alerts exist yet. Re-evaluating an event re-computes the result, and nothing prevents the same burst being reported for each of its events. De-duplication belongs to alert generation (Step 8).
- No automatic detection after ingestion; call the endpoints.
- At most 5000 events are read per rule evaluation. A burst larger than that for one source IP in a `2 x window_minutes` span could be truncated.
- Event matching is exact: no wildcards, regular expressions, ranges or negation in conditions, and metadata filters read top-level metadata keys only.
- One sequence shape only (N earlier events, then the trigger) and one correlation field per rule.
- Timestamps are those reported by the source (or ingestion time, flagged in metadata). Late-arriving or clock-skewed logs can change results when re-evaluated.
- Syslog timestamps without a year or time zone are assumed UTC by the Step 5 parser, which affects window calculations for such logs.
- There is no API for managing rules yet; use the seed script or MongoDB directly.
