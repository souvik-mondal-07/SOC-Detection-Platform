# Alert Generation (Step 8)

Converts successful detection-rule matches into persistent SOC alerts stored in the `alerts` MongoDB collection.

## Detection-to-alert flow

```text
Security Event -> DetectionService -> DetectionEngine -> DetectionResult (matched)
      -> AlertService -> AlertRepository -> MongoDB `alerts`
```

Responsibilities stay separate: ingestion, the rule evaluator and the engine never create alerts or touch the `alerts` collection. `AlertService` (`app/services/alert_service.py`) contains no detection logic; it consumes `DetectionResult`s. Alerts are created only when a client calls the alert generation endpoints (detection does not run automatically after ingestion).

## Alert schema

| Field | Notes |
|---|---|
| `alert_id` | `ALT-YYYYMMDD-NNNNNN`, server-generated, unique index. Not the Mongo `_id`. |
| `rule_id` | Rule that matched |
| `title` | `"{rule.name} Detected"` |
| `description` | Rule, reason, source IP, contributing event count, window; ends with "requires investigation" (no claims of confirmed attacks) |
| `severity` | `low` / `medium` / `high` / `critical`, copied from the rule |
| `status` | `open` on creation. Model also allows `investigating`, `resolved`, `false_positive` for the later management step (not implemented) |
| `source_ip` | From the detection context (correlation value when correlating on `source_ip`, else the evaluated event's IP); `null` if unknown, never invented |
| `event_ids` | IDs of contributing events only (no event documents copied) |
| `created_at`, `updated_at` | Server-generated UTC |

## Severity mapping

The rule stored in MongoDB is the source of truth. The alert severity is read from the rule; neither the event payload nor the detection result can override it.

## Alert IDs

The next number for the UTC day is the highest stored ID for that day plus one. If two writers pick the same number, the unique index rejects one and the service retries (up to 5 times).

## Duplicate prevention

An alert is skipped when an **open** alert already exists with the same `rule_id`, the same `source_ip` (or both null) and at least one shared event ID. Re-evaluating the same event, or another event of the same burst, creates no new alert. A new burst with no shared events, or any burst after the earlier alert is no longer `open`, creates a new alert.

## MongoDB storage and indexes

Collection `alerts`. Indexes (created by Step 3, idempotent): unique `alert_id`; `created_at`; `(status, created_at)`; `(severity, created_at)`; `(rule_id, created_at)`; `(source_ip, created_at)`. No new indexes were needed.

## API (`/api/v1/alerts`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/generate/{event_id}` | Evaluate one event, store alerts (404 if event missing) |
| POST | `/generate` | Body `{"event_ids": [...]}` (max 500). Unknown events are listed in `failed_events`; others still processed |
| GET | `/` | Filters `status`, `severity`, `rule_id`, `source_ip`; `page`, `limit` (max 100); paginated in MongoDB, newest first |
| GET | `/{alert_id}` | Full alert, 404 if missing |

Clients cannot supply `alert_id`, `severity`, `status`, `rule_id` or timestamps (request bodies reject unknown fields). Errors never include stack traces or connection details; a database outage returns 503.

## Current limitations

- Deduplication is a read-then-write check; two simultaneous requests could both create an alert for the same burst.
- A growing burst does not extend an existing alert's `event_ids`.
- Alerts are created on request only, not automatically on ingestion.
- No status transitions, investigation workflow, notifications, authentication or UI (later steps).
