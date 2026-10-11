# SOC Dashboard (Step 10)

A read-only React dashboard over the existing FastAPI backend. It has no mock data and never falls back to fake values: if a request fails, the section shows an error with a retry button.

## Architecture

```
React pages ──> hooks (useAsync + refresh) ──> services/api.ts ──> FastAPI /api/v1
                                   └─> lib/aggregate.ts (pure counting/bucketing)
```

- **`services/api.ts`** is the only code that calls `fetch`. It reads `VITE_API_BASE_URL`, turns network failures, HTTP errors (both backend error shapes) and unexpected response shapes into an `ApiError`, and shares identical in-flight GET requests.
- **Cancellation:** an `AbortSignal` is passed to the real `fetch()`. Identical in-flight GETs share one network call that is reference counted: it is cancelled only when every consumer has aborted, so one component unmounting or changing filters cannot cancel a request another component still needs. `AbortError` is treated as cancellation and is never shown as an API failure.
- **Hooks** (`hooks/`) wrap requests in `useAsync`: a new run aborts the previous one, so requests never overlap. A refresh keeps the loaded data on screen. If a refresh fails, the data and `updatedAt` are kept and a non-blocking "Could not refresh" banner with a Retry button is shown (`refreshError`); initial-load failures are a separate full error state. `updatedAt` changes only after a successful response. The backend indicator is the exception: a failed health refresh shows "Backend offline".
- **Response guards** (`services/guards.ts`) check every field the tables, detail views and charts read. A response in an unexpected format becomes a readable error instead of a render-time crash.
- **Layout** (`components/layout/`) owns one refresh counter (manual button and optional timer). The timer is cleared on unmount and skips ticks while the browser tab is hidden. The top bar's "Last updated" shows the page's last successful retrieval.
- **`lib/aggregate.ts`** holds the pure functions behind the charts (`countBy`, `bucketByTime`).

## Component structure (`frontend/src`)

| Folder | Contents |
| --- | --- |
| `types/` | Interfaces mirroring the backend models: alerts, events, rules, health |
| `services/` | `api.ts` API client |
| `hooks/` | `useAsync`, `useRefresh` (layout context), `useAlerts`, `useRules`, `useEvents`, `useDashboard`, `useBackendHealth` |
| `pages/` | Dashboard, Alerts, Security Events, Detection Rules, Investigations (placeholder), Settings |
| `components/layout/` | Responsive sidebar, top bar (health, refresh, last updated) |
| `components/dashboard/` | KPI cards, section loading/error wrapper, recent events, backend panel |
| `components/charts/` | Recharts bar charts and the alert trend chart |
| `components/alerts/`, `components/rules/`, `components/events/` | Filters, tables and read-only detail panels |
| `components/common/` | Badges, pagination, drawer, skeletons, error and empty states |

## Visual design

A dark "command center" theme built only with the existing Tailwind setup (no new dependencies, no web fonts, no icon library).

- **Tokens** live in `src/index.css` (`@theme`): void/panel/line surfaces, neon green and cyan accents, and severity colours (critical red, high orange, medium amber, low green). Shared classes: `panel`, `btn`, `btn-primary`, `field`, `field-label`, `tech-label`. Chart hex values are mirrored in `components/charts/theme.ts` because SVG attributes cannot use Tailwind classes.
- **Effects** are static CSS: a faint grid, two soft radial washes and barely visible scanlines on the page background. There are no looping animations, and `prefers-reduced-motion` disables transitions. Focus rings are neon and always visible.
- **Type:** system sans for interface text; a monospace stack (Cascadia Mono, JetBrains Mono, Consolas) for IPs, IDs, timestamps and small labels.
- **Threat posture strip:** one bar on the dashboard showing all stored alerts by severity, drawn from the exact per-severity counts. It shows an empty state, never placeholder values, when there are no alerts.
- **Icons:** inline SVG in `components/common/Icons.tsx`.
- Behaviour, API calls, filters, pagination and read-only detail views are unchanged by the redesign.

## API endpoints used

| Endpoint | Used for |
| --- | --- |
| `GET /health` | Connection indicator (backend and database state) |
| `GET /alerts` (`status`, `severity`, `rule_id`, `source_ip`, `priority_min`, `priority_max`, `page`, `limit`) | Alerts table, KPI counts, charts |
| `GET /alerts/{alert_id}` | Alert details (description, event IDs, `updated_at` are not in the list response) |
| `GET /events` (`limit`, `source`, `event_type`, `status`, `source_ip`) | Events page, recent events, event charts |
| `GET /events/{event_id}` | Event details |
| `GET /rules` (`category`, `severity`, `enabled`, `name`, `page`, `limit`) | Rules page, rule count KPI |
| `GET /rules/{rule_id}` | Rule details |

No backend code was changed. The dashboard only sends `GET` requests.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend URL (`frontend/.env`, see `.env.example`). Public by design; never put secrets in it |

The backend's `CORS_ORIGINS` must include the frontend origin (default `http://localhost:5173`).

## Running (PowerShell)

Terminal 1, backend (MongoDB must be running):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Terminal 2, frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To get data, ingest synthetic events (`scripts/seed_database.py`, `POST /events/batch`), seed rules (`scripts/seed_detection_rules.py`) and generate alerts (`POST /alerts/generate`).

## Functionality

- **Dashboard:** KPI cards (total, open, high + critical alerts, security events, detection rules), alerts by severity and status, alert creation times (labelled "sampled alerts only" when the API holds more alerts than were read), events by type and source, top 5 priority alerts, recent events, backend status.
- **Alerts:** table (ID, title, severity, priority, status, source IP, rule, created) in the backend's fixed order (priority descending, then newest); filters for severity, status, rule ID, source IP and priority range; reset; pagination (10–100 per page); read-only details drawer with description, timestamps, priority reason and associated event IDs (linking to the event view).
- **Security Events:** existing Step 9 page with exact-match filters, plus loading skeleton and `?event=` deep links.
- **Detection Rules:** read-only list with filters, paging and a details drawer (description, conditions).
- **Refresh:** manual button and auto-refresh (Off, 30 s, 1 min default, 5 min).
- **Investigations** is shown as a disabled "Planned" item.

## Known limitations

- **Event totals:** `GET /events` has no total count, offset or time filter. The events KPI shows the exact number only when fewer than 500 events come back; otherwise it shows `500+` with a note. Event charts use the newest 500 events and say so.
- **Alert trend:** the alerts API sorts by priority and cannot filter or sort by time. The chart reads up to 5 pages (500 alerts) in priority order. When there are more alerts than that, it is titled "sampled alerts only" and states that it is not the trend of recent alerts; it is complete only when all alerts were read. A backend `created_after`/sort option or a stats endpoint would make it exact.
- **KPI cost:** exact alert counts come from 9 small requests (`limit=1`, reading `total`). A backend aggregation endpoint (`/alerts/stats`) would reduce this to one call.
- Alert status changes, investigations, rule management, authentication and notifications are out of scope for this step.
- The production bundle is about 670 kB (Recharts); route-level code splitting could reduce it.
- Tests (Vitest) cover the API client (errors, cancellation, request sharing), response guards, the `useAsync` refresh behaviour, filter validation and chart aggregation. There are no browser or full-page component tests in the repository.
