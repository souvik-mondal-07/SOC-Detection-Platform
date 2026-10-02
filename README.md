# SOC Detection Platform

Rule-Based Security Event Detection and Alerting System for Automated Identification of Suspicious Activities.

**Status: Step 3 (MongoDB integration and data models).** Backend health check (including database status), MongoDB connection, data models, repositories and indexes, plus a starter dashboard. Dashboard figures are sample placeholders, not real telemetry. There is no authentication, log ingestion or detection logic yet, and no API for events, alerts or rules.

**Stack:** FastAPI, React + TypeScript + Vite, Tailwind CSS, MongoDB (PyMongo), Pytest. Recharts comes in a later step.

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

The dashboard top bar shows "Backend online" when the frontend can reach this endpoint.

## 4. Tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

The tests use an in-memory MongoDB stand-in and need no running database. Two optional integration tests (skipped by default) check a real MongoDB using a throwaway database:

```powershell
$env:RUN_MONGO_INTEGRATION = "1"; python -m pytest tests/test_mongo_integration.py
```

Frontend type-check and production build:

```powershell
cd frontend
npm run build
```

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

## Project structure

See [docs/architecture/overview.md](docs/architecture/overview.md) for the current code layout.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/research.md](docs/research.md) | Review of Wazuh, Splunk, Elastic Security and Microsoft Sentinel from official documentation, and the project gap |
| [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) | Problem statement, objectives, scope, architecture, planned backend modules, event model, design decisions |
| [docs/architecture/detection-strategy.md](docs/architecture/detection-strategy.md) | Rule types and schema, initial rule catalogue, alert lifecycle, severity criteria, evaluation methodology |
| [docs/architecture/database.md](docs/architecture/database.md) | MongoDB choice, collections, fields, indexes, repositories, setup, seeding, verification |

The project is for **authorised environments and synthetic data only**.

## Known limitations

- Dashboard numbers are hard-coded samples and the dashboard does not read from MongoDB yet. Sidebar items other than Overview show a placeholder page.
- No authentication, log ingestion, detection rules or event/alert/rule APIs yet.
- Automated tests use an in-memory MongoDB stand-in; use the optional integration test to check a real server.
- CORS only allows `GET`; widen it when write endpoints are added.
