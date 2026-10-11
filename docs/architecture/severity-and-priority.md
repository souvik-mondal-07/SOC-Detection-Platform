# Severity and Alert Prioritization (Step 9)

Gives every alert a severity (from its rule) and a deterministic 0-100 `priority_score` so analysts can see what to investigate first. No machine learning or AI is involved.

## Flow

```text
Detection Rule -> rule.severity -> Alert.severity
Detection Result (event count, correlation) + newest event time
      -> PriorityService -> priority_score + priority_reason -> Alert -> MongoDB
```

Severity is read from the rule stored in MongoDB. Neither the event payload (even `metadata.severity`), the detection result nor the API client can change it or the score.

## Severity levels

Single source of truth: `app/core/severity.py` (scores and wording) on top of the existing `Severity` enum in `app/models/common.py`. The canonical stored and API form is **lowercase** (`low`, `medium`, `high`, `critical`), unchanged from Steps 3-8, so no data migration was needed.

| Severity | Base Score | Meaning                    |
| -------- | ---------: | -------------------------- |
| LOW      |         25 | Minor anomaly              |
| MEDIUM   |         50 | Suspicious activity        |
| HIGH     |         75 | Strong suspicious activity |
| CRITICAL |        100 | Potentially severe impact  |

- **LOW** - minor or low-risk behaviour: a few unusual HTTP errors, an isolated low-confidence anomaly.
- **MEDIUM** - worth investigating, not urgent: repeated failures below a high-risk threshold, unusual network behaviour, limited suspicious activity.
- **HIGH** - strong evidence of harmful activity: brute-force-like failed logins, a successful login after repeated failures, significant suspicious network activity.
- **CRITICAL** - reserved for potentially severe impact (confirmed privilege abuse, multi-stage detections). Not every serious-looking event is critical, and the current rules may have few or none.

## Priority calculation (`app/services/priority_service.py`)

```text
score = base(severity) + event-count boost + correlation boost + recency boost      (clamped to 0-100)
```

| Factor | Rule | Boost |
|---|---|---:|
| Event count | 2-4 contributing events / 5-19 / 20 or more | +2 / +5 / +8 |
| Correlation | detection grouped 2+ events by a shared value (e.g. source IP) | +3 |
| Recency | newest evaluated event is at most 15 minutes old / at most 60 minutes old | +3 / +1 |

Maximum total boost is 14, below the 25-point gap between severity bases, so context can never push an alert above a higher-severity alert and a LOW rule can never reach CRITICAL. Scores are clamped to 0-100 (CRITICAL stays at 100). The same inputs always give the same score.

Recency uses the timestamp of the evaluated event, so replaying old logs gets no boost. Future timestamps count as "just now" (still only +3).

`priority_reason` is a short plain sentence, e.g. `High severity rule with multiple correlated events and recent activity`. It does not expose weights or internals.

Examples: LOW, one old event = 25. AUTH-001 (HIGH), 5 failed logins from one IP, old events = 83; with recent events = 86. A synthetic CRITICAL rule = 100.

## Ordering, filtering, pagination

`GET /api/v1/alerts` sorts by `priority_score` descending, then `created_at` descending (then `alert_id` for a stable order). Filters: `severity`, `status`, `rule_id`, `source_ip`, `priority_min`, `priority_max` (0-100, min must not exceed max; otherwise 422). Filtering, sorting and paging all run inside MongoDB. `page` / `limit` (max 100) are unchanged. Responses include `priority_score` and `priority_reason`.

## MongoDB indexes (added in Step 9)

| Index | Why |
|---|---|
| `ix_priority_created_at` (`priority_score` desc, `created_at` desc) | Default list order and `priority_min` / `priority_max` range filters |
| `ix_status_priority_created_at` (`status`, `priority_score` desc, `created_at` desc) | The triage queue: open alerts ordered by priority |

The existing `severity`, `rule_id`, `source_ip` and `created_at` indexes are kept. They are created by `initialize_database` (idempotent).

## Limitations

- Alerts stored before Step 9 have no `priority_score` in MongoDB. They read back with their severity's base score, but are not matched by `priority_min` / `priority_max` and sort after scored alerts until backfilled. No backfill is included.
- The score is fixed at creation and is not refreshed as an alert ages or a burst grows.
- Weights are constants in `priority_service.py`, not configurable per rule or at runtime.
- Priority does not consider asset value, user role or threat intelligence.
