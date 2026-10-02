# SOC Detection Platform

Rule-Based Security Event Detection and Alerting System for Automated Identification of Suspicious Activities.

**Status: Step 1 (foundation).** Backend health check and a starter dashboard only. Dashboard figures are sample placeholders, not real telemetry. There is no database, authentication, log ingestion or detection logic yet.

**Stack:** FastAPI, React + TypeScript + Vite, Tailwind CSS, Pytest. MongoDB and Recharts come in later steps.

## Prerequisites

- Python 3.11+ (`py --version`)
- Node.js 20+ (`node --version`)

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
  "timestamp": "2026-01-01T12:00:00.000000Z"
}
```

The dashboard top bar shows "Backend online" when the frontend can reach this endpoint.

## 4. Tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Frontend type-check and production build:

```powershell
cd frontend
npm run build
```

## Configuration

| File | Variable | Purpose |
| --- | --- | --- |
| `backend/.env` | `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API |
| `backend/.env` | `ENVIRONMENT`, `APP_NAME`, `APP_VERSION` | Reported by the health endpoint |
| `frontend/.env` | `VITE_API_BASE_URL` | Backend URL (default `http://localhost:8000/api/v1`) |

`.env` files are git-ignored. Only the `.env.example` files are committed, and they contain no secrets.

## Project structure

See [docs/architecture/overview.md](docs/architecture/overview.md).

## Known limitations

- Dashboard numbers are hard-coded samples. Sidebar items other than Overview show a placeholder page.
- No database, authentication, log ingestion or detection rules yet.
- CORS only allows `GET`; widen it when write endpoints are added.
