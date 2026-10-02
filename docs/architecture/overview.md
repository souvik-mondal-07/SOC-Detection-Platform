# Architecture Overview (Step 1)

This page describes the code as built in Step 1. The full design is in [system-architecture.md](system-architecture.md). MongoDB models, repositories and indexes (Step 3) are described in [database.md](database.md).

Lightweight SOC monitoring platform: a FastAPI backend and a React + TypeScript frontend, with MongoDB planned for a later step.

## Layout

```text
backend/app/
  main.py          App factory: CORS, error handlers, router mounting
  api/             HTTP layer. router.py collects versioned routers (api/v1/...)
  core/            Cross-cutting code: config (env vars), error handling
  services/        Business logic (future: ingestion, detection engine, alert management)
  models/          Data schemas (future: events, alerts, rules, users)
  repositories/    Database access (future: MongoDB)
frontend/src/
  components/      layout/ (Sidebar, TopBar) and dashboard/ (cards, panels)
  config/          Static configuration such as navigation items
  hooks/           React hooks (backend health check)
  services/        API client functions
  types/           TypeScript types mirroring API responses
```

## Layering rule

`api` -> `services` -> `repositories`. Routes stay thin, services hold logic, and only repositories talk to the database. This lets MongoDB be added later without touching routes or logic.

## Where future features plug in

| Feature | Place |
| --- | --- |
| MongoDB | `repositories/` plus a connection helper in `core/` |
| Log ingestion | new router in `api/v1/`, logic in `services/` |
| Detection rules | `models/` for rule schemas, `services/` for the engine |
| Alert management | router, service and repository for alerts |
| Authentication | dependency in `core/`, applied to routers in `api/router.py` |

## Current API

`GET /api/v1/health` returns service status. All errors return `{"error": {"message": "..."}}`.
