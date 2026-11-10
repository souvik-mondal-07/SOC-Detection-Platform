# Alert Lifecycle (Step 12)

Analysts can acknowledge an alert, move it into investigation, resolve it, mark it as a false positive, and reopen a closed alert. Every change is validated on the server, applied atomically, and recorded in a status history on the alert.

Related: [alert-generation.md](alert-generation.md), [severity-and-priority.md](severity-and-priority.md), [alert-investigation.md](alert-investigation.md), [soc-dashboard.md](soc-dashboard.md).

> **No authentication yet.** The lifecycle endpoints change alert state and are for the local development environment only. Authentication and role-based authorization must exist before they are exposed anywhere else (see [Security limitations](#security-limitations)).

## Design decisions

| Decision | Choice | Why |
|---|---|---|
| Is "acknowledged" a status? | **No.** It is an `acknowledged_at` timestamp on an alert whose status is still `open`. | The four existing statuses, the `status` filter, the dashboard counts and open-alert de-duplication (`find_open_duplicate` matches `status == "open"`) keep working unchanged. A new status would have changed all of them. |
| Where is the logic? | `AlertService.change_status` / `acknowledge`. | Routes only translate HTTP. MongoDB operations stay in `AlertRepository`. |
| Alert status vs investigation status | Fully separate. | Closing an investigation never resolves its alerts; resolving an alert never closes an investigation. Both are tested. |
| Actor attribution | **Not recorded.** | There is no authentication, so an analyst identity would be fabricated. History entries have no actor field. |

## Statuses

| Status | Meaning |
|---|---|
| `open` | New or reopened. May additionally be *acknowledged* (`acknowledged_at` set). |
| `investigating` | An analyst is working on it. |
| `resolved` | Handled. Carries a resolution note. |
| `false_positive` | Not a real threat. Carries a reason. |

"Active" means `open` or `investigating`.

## Allowed transitions

| From → To | `open` | `investigating` | `resolved` | `false_positive` |
|---|---|---|---|---|
| **open** | n/a | yes | yes (note required) | yes (reason required) |
| **investigating** | yes | n/a | yes (note required) | yes (reason required) |
| **resolved** | yes (reason required, "reopen") | no | n/a | no |
| **false_positive** | yes (reason required, "reopen") | no | no | n/a |

- Re-requesting the current status is rejected (409), not silently accepted, so a repeated click never writes a duplicate history entry.
- Acknowledge is allowed only for an `open` alert that has no `acknowledged_at`.
- Reopening clears `resolution_note` and `acknowledged_at` (the alert returns to the triage queue). The old note stays in the history.
- The table lives in `backend/app/models/alert.py` (`ALLOWED_TRANSITIONS`) and is mirrored in `frontend/src/types/alerts.ts` (`ALERT_TRANSITIONS`). The UI only offers valid actions; the backend enforces them.

## API

Base path `/api/v1/alerts`. Errors use the existing shape `{"error": {"message": "..."}}`; validation errors add `details`.

| Endpoint | Purpose | Success |
|---|---|---|
| `PATCH /alerts/{alert_id}/status` | Change status | 200 `AlertResponse` |
| `POST /alerts/{alert_id}/acknowledge` | Acknowledge an open alert (no body) | 200 `AlertResponse` |
| `GET /alerts/stats` | Exact lifecycle counts | 200 `AlertStatsResponse` |
| `GET /alerts`, `GET /alerts/{alert_id}` | Existing; now also return `acknowledged_at` (list) and `resolution_note`, `status_history` (detail) | 200 |

Error codes: **404** unknown alert, **409** disallowed transition or the alert was changed concurrently, **422** invalid status, missing or too long reason, unknown field, malformed ID, **503** database unavailable (no connection details leaked).

### Change status

Request body (exactly these fields; anything else, such as `severity` or `priority_score`, is a 422):

```json
{ "status": "resolved", "reason": "Password reset and user confirmed the logins." }
```

- `status`: one of `open`, `investigating`, `resolved`, `false_positive`.
- `reason`: optional text of at most 1000 characters; whitespace is trimmed and a blank value counts as missing. **Required** for `resolved` (resolution note), `false_positive` (reason) and any reopen.

Response:

```json
{
  "success": true,
  "alert": {
    "alert_id": "ALT-20261105-000001",
    "rule_id": "AUTH-001",
    "title": "Multiple Failed Logins Detected",
    "severity": "high",
    "priority_score": 83,
    "priority_reason": "High severity rule with multiple correlated events",
    "status": "resolved",
    "source_ip": "192.168.1.20",
    "created_at": "2026-11-05T10:00:00Z",
    "acknowledged_at": "2026-11-05T10:05:00Z",
    "description": "...",
    "event_ids": ["evt_00001", "evt_00002"],
    "updated_at": "2026-11-05T10:30:00Z",
    "resolution_note": "Password reset and user confirmed the logins.",
    "status_history": [
      { "action": "acknowledged", "previous_status": "open", "new_status": "open", "timestamp": "2026-11-05T10:05:00Z", "reason": null },
      { "action": "status_change", "previous_status": "open", "new_status": "resolved", "timestamp": "2026-11-05T10:30:00Z", "reason": "Password reset and user confirmed the logins." }
    ]
  }
}
```

Example errors:

```json
{ "error": { "message": "A resolution note is required" } }                                   // 422
{ "error": { "message": "An alert that is resolved cannot be changed to investigating" } }     // 409
{ "error": { "message": "The alert was changed by someone else. Reload it and try again" } }  // 409
{ "error": { "message": "Alert not found" } }                                                  // 404
```

### Stats

`GET /alerts/stats` runs one aggregation (plus one count) inside MongoDB. It never depends on how many alerts a client fetched.

```json
{
  "success": true,
  "total": 6,
  "by_status": { "open": 3, "investigating": 1, "resolved": 1, "false_positive": 1 },
  "by_severity": { "low": 1, "medium": 1, "high": 2, "critical": 2 },
  "active": 4,
  "high_critical_active": 2,
  "acknowledged_open": 1
}
```

`high_critical_active` counts alerts with severity `high` or `critical` **and** status `open` or `investigating`. The route is declared before `/{alert_id}` so `stats` is never read as an alert ID.

## Status history

Stored on the alert document as `status_history` (oldest first):

| Field | Meaning |
|---|---|
| `action` | `status_change`, or `acknowledged` (status stays `open`, so `previous_status == new_status`) |
| `previous_status` | Status before the change |
| `new_status` | Status after the change |
| `timestamp` | UTC time of the change (equals the alert's new `updated_at`) |
| `reason` | The note or reason, if any |

There is **no actor field**: authentication is not implemented, so a change cannot be attributed to a person. Add one only when real identities exist.

The list is capped at the newest 200 entries (`$push` with `$slice`). Current outcome is also kept in `resolution_note` for resolved and false-positive alerts.

## Integrity and concurrency

- `AlertRepository.apply_transition` is one `update_one` whose filter includes the status the service validated against (and `acknowledged_at: null` for acknowledgement). Two concurrent requests cannot both apply; the loser gets 409 and nothing is overwritten. The status-history entry is appended in the same atomic update.
- The update `$set`s only `status`, `updated_at`, `acknowledged_at` and `resolution_note`. Severity, priority score and reason, rule ID, source IP, event references, title and description are never written, and no detection runs, so a status change cannot create or regenerate alerts.
- `updated_at` is set on every change and is never earlier than `created_at`.
- Reopening puts an alert back to `open`. If detection later matches the same events again, the existing de-duplication will treat the reopened alert as the open one, as designed in Step 8.

## Backward compatibility

All new alert fields are optional with defaults (`acknowledged_at = None`, `resolution_note = None`, `status_history = []`). Alerts stored by Steps 8–11 load and can be transitioned without migration, and an alert stored with no `status` is treated as `open`. The API's existing fields, filters and sort order are unchanged. No new indexes were needed: `ix_status_*` already serve the status filter, and the history is only read with its alert.

## Dashboard integration

- **Alerts table:** status badge with an `ack` marker for acknowledged open alerts, and an *Actions* column with **Ack** and **Investigate** shortcuts (disabled when invalid, and while any request is running). A success or error notice appears after the backend answers, then the list and metrics refresh.
- **Alert details drawer** (opened from the Alerts page and the Dashboard): status badge, valid actions only, an inline confirmation with a required reason for **Resolve**, **Mark false positive** and **Reopen**, a status-history timeline (newest first), and the investigations that reference the alert (link to `/investigations/{id}`, shown with an explicit "Investigation status" label).
- Success is shown only after the API replies. Buttons are disabled while a request is in flight and a second submit in the same tick is ignored. After success the drawer shows the backend's confirmed alert, refetches it, and the page refreshes the alert list and dashboard metrics.
- **Filters:** the existing status filter (`open`, `investigating`, `resolved`, `false positive`) still maps to the backend `status` parameter. Empty results show the existing empty state.
- **Metrics:** Open (with acknowledged count), Investigating, Resolved, False positives and *High + critical active* come from `GET /alerts/stats`.
- Priority-score ordering and severity filters are unchanged.

## Investigation integration

Uses the existing `GET /investigations?alert_id=` filter; no investigation code or data changed. Resolving an alert does not touch its investigations, and closing an investigation does not touch its alerts (covered by `test_alert_and_investigation_status_are_independent`). Alert-to-investigation links are preserved.

## Security limitations

- **No authentication or authorization.** Anyone who can reach the API can change alert states. Add authentication and role-based authorization (and then an `actor` on history entries) before use beyond local development.
- Input is validated server-side: status is an enum, `reason` is length-limited, unknown fields are rejected (so severity, priority and `$`-operators cannot be smuggled in), IDs are pattern-checked, and clients never supply MongoDB filters.
- Errors never include stack traces or connection details. There is no `eval`/`exec`, and no synthetic alerts or history are created by the application.
- History is audit-friendly but not tamper-proof: anyone with database access can edit it.

## Commands (Windows PowerShell, from the project root)

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm run dev

# Backend tests (lifecycle tests only, then everything)
cd backend
python -m pytest tests/alerts/test_alert_lifecycle.py -q
python -m pytest -q

# Frontend tests, type check and production build
cd frontend
npm test
npx tsc -b
npm run build
```

Try it by hand: generate an alert (`POST /api/v1/alerts/generate/{event_id}`), then in http://localhost:8000/docs run `POST /alerts/{id}/acknowledge` and `PATCH /alerts/{id}/status` with `{"status": "resolved", "reason": "..."}`.

## Known limitations

- No actor on history entries (no authentication).
- Acknowledgement is single-step: there is no "unacknowledge" other than reopening a closed alert.
- Alerts cannot move directly between `resolved` and `false_positive`; reopen first.
- Status changes are not bulk operations; each alert is changed individually.
- The dashboard's "alerts over time" chart still samples up to 500 alerts (unchanged from Step 10); the lifecycle counts above are exact.
