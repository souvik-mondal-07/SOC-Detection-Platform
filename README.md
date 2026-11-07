# SOC Detection Platform

Rule-Based Security Event Detection and Alerting System for Automated Identification of Suspicious Activities.

**Status: Step 11 (alert investigation workflow) on top of Steps 1–10.** The backend accepts security events as JSON or as raw logs (Linux auth, web access, Windows event, network), validates and normalizes them, stores them in MongoDB, and returns them through a small read API. A rule-based detection engine can be run on stored events on request; it returns detection results only. Alerts can be generated from detection matches (Step 8) and are prioritised with a 0–100 score (Step 9). The React dashboard (Step 10) shows alerts, security events and detection rules in read-only list and detail views, with Recharts visualisations. Analysts can open investigations for alerts, link alerts, add notes and track investigation status (Step 11, [details](docs/architecture/alert-investigation.md)). There is no authentication yet, so the API is for local development only.

**Stack:** FastAPI, React + TypeScript + Vite, Tailwind CSS, MongoDB (PyMongo), Recharts, Pytest, Vitest.

## Prerequisites

- Python 3.11+ (`py --version`)
- Node.js 20+ (`node --version`)
- MongoDB Community Server running locally (see [MongoDB setup](#mongodb-setup)). The backend still starts without it, and the health endpoint reports `degraded`.

All commands are for Windows PowerShell, run from the project root (`SOC-Detection-Platform`).

## 1. Backend setup

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

If activation is blocked, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.

## 2. Frontend setup

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

## MongoDB setup

1. Install **MongoDB Community Server** for Windows from https://www.mongodb.com/try/download/community (run as a Windows Service, the default).
2. Check it is running: `Get-Service MongoDB` should show `Running` (start it from an administrator PowerShell with `Start-Service MongoDB`).
3. The defaults in `backend/.env.example` match a local install, so no edits are needed.

Details, collections and indexes: [docs/architecture/database.md](docs/architecture/database.md).

## 3. Run (two separate terminals)

Terminal 1, backend (from `backend`, venv activated):

```powershell
uvicorn app.main:app --reload --port 8000
```

Terminal 2, frontend (from `frontend`):

```powershell
npm run dev
```

- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

Expected health response:

```json
{
  "status": "ok",
  "message": "Backend is running",
  "service": "SOC Detection Platform",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected",
  "timestamp": "2026-01-01T12:00:00.000000Z"
}
```

If MongoDB is not reachable the endpoint still answers HTTP 200 with `"status": "degraded"` and `"database": "unavailable"` (it can take about 3 seconds to answer, the configured timeout). Collections and indexes are created automatically at startup when MongoDB is available. To run that step manually: `python -m app.repositories.initialization` (from `backend`).

The top bar shows "Backend online" when the frontend can reach this endpoint.

## 4. Tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

The tests (about 180) use an in-memory MongoDB stand-in and need no running database. Two optional integration tests (skipped by default) check a real MongoDB using a throwaway database:

```powershell
$env:RUN_MONGO_INTEGRATION = "1"; python -m pytest tests/test_mongo_integration.py
```

Frontend type-check and production build:

```powershell
cd frontend
npm run build
npm test
```

## Try the event ingestion API

With MongoDB and the backend running, open a second PowerShell window in `backend`:

```powershell
$base = "http://localhost:8000/api/v1"

# Load a synthetic sample file (JSON array) in one batch request
$events = Get-Content "..\sample_logs\failed_auth.json" -Raw | ConvertFrom-Json
$batch  = @{ events = @($events) } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri "$base/events/batch" -ContentType "application/json" -Body $batch

# Read the newest failed authentication events back
(Invoke-RestMethod -Uri "$base/events?event_type=authentication&status=failed&limit=20").events |
    Format-Table event_id, timestamp, status, username, source_ip
```

Endpoints: `POST /api/v1/events`, `POST /api/v1/events/batch`, `GET /api/v1/events`, `GET /api/v1/events/{event_id}`. Single-event, filter, 404 and validation-error examples are in [docs/architecture/event-ingestion.md](docs/architecture/event-ingestion.md). Interactive API docs: http://localhost:8000/docs.

## Seed development data (optional, manual only)

Inserts 8 synthetic events, 3 rules and 2 alerts. It never runs automatically, skips records that already exist and deletes nothing. From `backend` with the venv active:

```powershell
python ..\scripts\seed_database.py
```

## Configuration

| File | Variable | Purpose |
| --- | --- | --- |
| `backend/.env` | `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API |
| `backend/.env` | `ENVIRONMENT`, `APP_NAME`, `APP_VERSION` | Reported by the health endpoint |
| `backend/.env` | `MONGODB_URI`, `MONGODB_DATABASE` | MongoDB connection (defaults: `mongodb://localhost:27017`, `soc_detection_platform`) |
| `backend/.env` | `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | Wait time before MongoDB is reported unavailable (default 3000) |
| `frontend/.env` | `VITE_API_BASE_URL` | Backend URL (default `http://localhost:8000/api/v1`) |

`.env` files are git-ignored. Only the `.env.example` files are committed, and they contain no secrets.

## Supported log formats (Step 5)

Raw logs can be sent to `POST /api/v1/events/parse` (one log) or `POST /api/v1/events/parse/batch` (up to 500) with a `source_type`. Each is parsed, normalized with the Step 4 rules and stored through the existing ingestion pipeline.

| `source_type` | Format |
| --- | --- |
| `linux_auth` | sshd/PAM syslog lines: failed, accepted, invalid user, blocked |
| `web_application` | Common Log Format web access lines |
| `windows_event` | Simplified Windows Event JSON (Event ID 4624, 4625) |
| `network` | JSON or CSV connection records |

Synthetic samples are in `sample_logs/raw/`. Parsing does not detect anything; see [docs/architecture/log-parsing.md](docs/architecture/log-parsing.md).

## Detection engine (Step 6)

Stored events are evaluated against data-driven rules from the `detection_rules` collection. The engine answers "did this event match a rule?" and returns a structured result. It does **not** create alerts itself (the alert service from Step 8 does that) and does not run automatically after ingestion; you call it explicitly.

Create the five initial rules once (manual only, safe to repeat, never runs on startup). From `backend` with the venv active:

```powershell
python ..\scripts\seed_detection_rules.py
```

| Rule | Severity | Detects |
| --- | --- | --- |
| `AUTH-001` | high | 5 failed authentication events from one source IP within 5 minutes |
| `AUTH-002` | medium | Failed login for a nonexistent user (parser metadata `reason = invalid_user`) |
| `AUTH-003` | high | Successful login after 3 or more failures from the same IP within 10 minutes |
| `WEB-001` | medium | 10 HTTP 403/404 responses to one source IP within 5 minutes |
| `NET-001` | medium | One source IP reaching 10 distinct destination ports within 5 minutes |

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/detection/evaluate/EVENT_ID" -Method POST
```

`POST /api/v1/detection/evaluate/{event_id}` evaluates one event and `POST /api/v1/detection/evaluate` takes `{"event_ids": [...]}` (up to 500). Matches are indicators of suspicious activity that need investigation, not proof of an attack. See [docs/architecture/detection-engine.md](docs/architecture/detection-engine.md).

## Alert Generation

Matched detection results can be turned into persistent alerts (collection `alerts`). `POST /api/v1/alerts/generate/{event_id}` and `POST /api/v1/alerts/generate` run detection and store one `open` alert per matching rule; severity comes from the rule, events are referenced by ID, and repeat evaluations of the same burst are deduplicated. `GET /api/v1/alerts` (filters `status`, `severity`, `rule_id`, `source_ip`, `priority_min`, `priority_max`; `page`, `limit`) and `GET /api/v1/alerts/{alert_id}` read them. Status management, investigation workflow and the alerts UI are not implemented yet. See [docs/architecture/alert-generation.md](docs/architecture/alert-generation.md).

## Alert Prioritization

Every alert has the severity of its rule (`low`, `medium`, `high`, `critical`) and a deterministic `priority_score` from 0 to 100 with a short `priority_reason`. The score starts from the severity (25 / 50 / 75 / 100) and adds small capped boosts for contributing event count, correlation and recency; context can never outrank a higher severity. `GET /api/v1/alerts` returns highest priority first (ties: newest first) and supports `severity`, `status`, `rule_id`, `source_ip`, `priority_min` and `priority_max`. Clients cannot set severity or score. See [docs/architecture/severity-and-priority.md](docs/architecture/severity-and-priority.md).

## Detection Rule Management (Step 7)

Detection rules are managed through `/api/v1/rules`. MongoDB (`detection_rules`) is the single source of truth: the detection engine reads the enabled rules from it on every evaluation, so creating, editing, disabling or deleting a rule takes effect immediately with no restart.

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/rules` | List rules. Filters: `category`, `severity`, `enabled`, `name`. Paging: `page`, `limit` (max 100) |
| `GET /api/v1/rules/{rule_id}` | Full rule configuration |
| `POST /api/v1/rules` | Create a rule (`201`; duplicate `rule_id` gives `409`) |
| `PUT /api/v1/rules/{rule_id}` | Update name, description, category, severity, enabled or conditions (`rule_id` is immutable) |
| `PATCH /api/v1/rules/{rule_id}/status` | Body `{"enabled": false}` enables or disables a rule |
| `DELETE /api/v1/rules/{rule_id}` | Delete a rule. The five initial rules need `?force=true` |

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/rules?category=authentication&enabled=true"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/rules/AUTH-001/status" -Method PATCH -ContentType "application/json" -Body '{"enabled": false}'
```

Rules are plain data validated against the engine's own condition vocabulary; code is never accepted or evaluated. Errors use `{"success": false, "message": "...", "error_code": "RULE_NOT_FOUND"}`. There is no authentication yet, so the rule API is open like the rest of the API. See [docs/architecture/detection-rules.md](docs/architecture/detection-rules.md).

## Frontend pages

The React app uses React Router with one shared layout (sidebar and top bar). Pages live in `frontend/src/pages/`.

| Route | Page | Backend data |
| --- | --- | --- |
| `/dashboard` | Dashboard | KPI cards, charts and top alerts from `GET /alerts`, `GET /events`, `GET /rules`, `GET /health` |
| `/alerts` | Alerts | `GET /alerts` (filters, paging) and `GET /alerts/{id}`; read-only |
| `/security-events` | Security Events | `GET /events` (filters: event type, status, source, source IP, limit) and `GET /events/{id}` |
| `/detection-rules` | Detection Rules | `GET /rules` and `GET /rules/{id}`; read-only |
| `/investigations` | Investigations | Planned for a later step (disabled in the sidebar) |
| `/settings` | Settings | Read-only app, API and backend information; no secrets |

The frontend shows only data returned by the backend and contains no sample or mock data. The events API has no paging or total count, so event figures are labelled as "newest N". See [docs/architecture/soc-dashboard.md](docs/architecture/soc-dashboard.md) for the architecture and known limitations. After pulling this version run `npm install` in `frontend` (it added `recharts` and `vitest`).

## Project structure

See [docs/architecture/overview.md](docs/architecture/overview.md) for the current code layout.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/research.md](docs/research.md) | Review of Wazuh, Splunk, Elastic Security and Microsoft Sentinel from official documentation, and the project gap |
| [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) | Problem statement, objectives, scope, architecture, planned backend modules, event model, design decisions |
| [docs/architecture/severity-and-priority.md](docs/architecture/severity-and-priority.md) | Severity levels, priority score formula, ordering, indexes, limitations |
| [docs/architecture/detection-strategy.md](docs/architecture/detection-strategy.md) | Rule types and schema, initial rule catalogue, alert lifecycle, severity criteria, evaluation methodology |
| [docs/architecture/database.md](docs/architecture/database.md) | MongoDB choice, collections, fields, indexes, repositories, setup, seeding, verification |
| [docs/architecture/event-ingestion.md](docs/architecture/event-ingestion.md) | Event lifecycle, endpoints, schema, sample requests and responses, error behavior, PowerShell test commands |
| [docs/architecture/event-normalization.md](docs/architecture/event-normalization.md) | Normalization rules, alias tables, supported sources, event types and statuses, timestamp handling |
| [docs/architecture/log-parsing.md](docs/architecture/log-parsing.md) | Parser layer, registry, supported raw formats, parse endpoints, errors, examples |
| [docs/architecture/detection-engine.md](docs/architecture/detection-engine.md) | Rule model, stateless and stateful evaluation, thresholds, windows, correlation, results, initial rules, security, limitations |
| [docs/architecture/detection-rules.md](docs/architecture/detection-rules.md) | Rule structure, categories, severities, condition fields, lifecycle, rule API, validation, storage, engine integration |

The project is for **authorised environments and synthetic data only**.

## Known limitations

- The dashboard is read-only. Alerts and detection rules have list and detail views; Investigations, alert status management, rule management (create, edit, enable, delete), authentication and notifications are not part of Step 10 and are not implemented in the UI. The Investigations item is a disabled placeholder.
- `GET /events` has no paging or total count, and `GET /alerts` cannot be sorted or filtered by time, so some dashboard figures describe the newest events or a sample of alerts and are labelled that way (see [docs/architecture/soc-dashboard.md](docs/architecture/soc-dashboard.md)).
- No authentication yet: the event API is open to anyone who can reach it, so run it locally with synthetic or authorized data only.
- Detection results are not stored; alerts are created only on request via the alert API (no status management yet), and parsing covers only the formats listed above.
- Automated tests use an in-memory MongoDB stand-in; use the optional integration test to check a real server.
- CORS allows `GET`, `POST`, `PUT`, `PATCH` and `DELETE` from the configured frontend origins only.
