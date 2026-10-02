# Database Architecture (Step 3)

MongoDB is the only database. Nothing here stores authentication data, and no detection logic runs yet.
Related: [system-architecture.md](system-architecture.md) (overall design), [detection-strategy.md](detection-strategy.md) (rules and alerts).

## 1. Why MongoDB

Events from different sources carry different optional details (a web request has a path and status code, a network event has ports). A document database stores these without a wide table of mostly empty columns, and the free-form `metadata` and rule `conditions` fit it naturally. MongoDB is also a stated project requirement, and SQL databases are excluded. The official Python driver, `pymongo`, is used (synchronous; FastAPI runs the sync routes in a thread pool).

## 2. Database and collections

Database name: `soc_detection_platform` (configurable with `MONGODB_DATABASE`).

| Collection | Holds | Unique ID field |
| --- | --- | --- |
| `security_events` | Normalised security events | `event_id` |
| `alerts` | Alerts created from rule matches | `alert_id` |
| `detection_rules` | Rule definitions | `rule_id` |
| `investigations` | Investigation records grouping alerts, with notes | `investigation_id` |

User/authentication collections will be added with authentication in a later step.

## 3. Important fields

All models are Pydantic classes in `backend/app/models/`. They reject unknown fields, store enums as plain strings, and use timezone-aware UTC datetimes (naive datetimes are rejected).

**`security_events`** (`models/event.py`)

| Field | Rules |
| --- | --- |
| `event_id` | Required, unique, letters/digits/`_`/`-`, max 64 chars |
| `timestamp` | Required, must include a timezone, stored as UTC |
| `source` | Required, lowercase snake_case (e.g. `linux_auth`) |
| `event_type` | `authentication`, `web`, `network`, `privilege` |
| `action` | Required, lowercase snake_case (e.g. `login`) |
| `status` | `success`, `failed`, `unknown` |
| `username`, `source_ip` | Optional. `source_ip` must be a valid IPv4/IPv6 address |
| `message` | Required, 1 to 1000 chars |
| `metadata` | Free-form object. Keys that look like credentials (`password`, `secret`, `token`, `api_key`...) or that start with `$` / contain `.` are rejected |
| `created_at` | Set automatically (UTC) |

The model checks `metadata` keys, not free text. Parsers written in Step 4 must not copy credentials into `message`.

**`alerts`** (`models/alert.py`): `alert_id`, `rule_id` (format `AUTH-001`), `title`, `description`, `severity` (`low` `medium` `high` `critical`), `status` (`open` `investigating` `resolved` `false_positive`, default `open`), optional `source_ip`, `event_ids` (at least one, no duplicates), `created_at`, `updated_at` (cannot be earlier than `created_at`).

**`detection_rules`** (`models/rule.py`): `rule_id`, `name`, `category` (`authentication` `web` `network` `privilege` `correlation`), `description`, `severity`, `enabled` (true/false only, default true), `conditions`, timestamps. `conditions` is a free-form object that must be non-empty and use MongoDB-safe keys. The detection engine will define how it is interpreted, so adding rules or rule shapes needs no schema migration.

**`investigations`** (`models/investigation.py`): `investigation_id`, `alert_ids` (at least one), `title`, `status` (`open` `in_progress` `closed`, default `open`), `notes` (list of `{text, created_at}`), timestamps.

## 4. Indexes

Defined next to each repository and created by the initialization step. Compound indexes begin with the filtered field, so they also serve lookups on that field alone. That is why there is no separate single-field index for `source_ip`, `username`, `event_type` and similar.

**`security_events`**

| Index | Why |
| --- | --- |
| `uq_event_id` (unique) | Guarantees no duplicate events; fast lookup by ID |
| `ix_timestamp` (desc) | Newest-first listing and time-range queries |
| `ix_source_ip_timestamp` | "All events from this IP over time", used in investigation and for per-IP rule windows |
| `ix_event_type_timestamp` | Rules read one event type within a time window |
| `ix_username_timestamp` | Activity of a single account |

**`alerts`**

| Index | Why |
| --- | --- |
| `uq_alert_id` (unique) | Guarantees unique alert IDs |
| `ix_created_at` (desc) | Newest alerts first |
| `ix_status_created_at` | Triage queue (open alerts, newest first) |
| `ix_severity_created_at` | Filter by severity |
| `ix_rule_id_created_at` | Alerts per rule, used when tuning rules |
| `ix_source_ip_created_at` | Alerts for one address |

**`detection_rules`**: `uq_rule_id` (unique), `ix_category` (list by category), `ix_enabled` (engine loads enabled rules). The collection will stay small, so these exist mostly for the unique ID and for clarity.

**`investigations`**: `uq_investigation_id` (unique), `ix_status_created_at` (open investigations first), `ix_created_at`.

Each index costs some write time and disk. The set is kept small on purpose and should be revisited with real query patterns in later steps.

## 5. Code layout

```text
backend/app/
├── core/
│   ├── config.py         Reads MONGODB_* settings
│   ├── database.py       One shared MongoClient, get_database(), check_connection(), close_client()
│   └── errors.py         DatabaseUnavailableError -> HTTP 503 JSON error
├── models/               common.py, event.py, alert.py, rule.py, investigation.py
└── repositories/
    ├── base.py           BaseRepository: create, find_by_id, find_many, update
    ├── event_repository.py / alert_repository.py / detection_rule_repository.py / investigation_repository.py
    └── initialization.py Creates collections and indexes
```

Layering is unchanged: `api` -> `services` -> `repositories`. Only repositories touch MongoDB, and each receives the database in its constructor, so tests can pass an in-memory stand-in.

- **Connection:** the client is created lazily and reused (the driver pools connections). The app starts even if MongoDB is down.
- **Repository operations:** `create` (raises `DuplicateRecordError` on a duplicate ID), `find_by_id`, `find_many` (query, sort, `limit` up to 1000, `skip`), and `update` (partial; the merged record is re-validated, so an invalid status can never be stored). There is **no delete**, since nothing needs it yet. `find_many` takes a query from trusted code. When APIs are added, the API layer must build queries from allowed filters, not pass user input straight through.
- **Errors:** connection failures become `DatabaseUnavailableError` and the API answers 503 with `{"error": {"message": "Database is unavailable"}}`. No URI or credentials appear in responses or logs.

## 6. Initialization

`initialize_database()` checks MongoDB is reachable, creates the four collections if missing, and creates missing indexes. It never drops, truncates or edits data and is safe to repeat. It runs automatically at backend startup in a best-effort way: if MongoDB is down, a warning is logged and the app still starts. It also runs before seeding. To run it by hand (from `backend`, venv active):

```powershell
python -m app.repositories.initialization
```

If an existing collection already holds duplicate IDs, creating a unique index will fail and the error is logged. Nothing is changed automatically.

## 7. Environment variables (`backend/.env`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DATABASE` | `soc_detection_platform` | Database name |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | `3000` | How long to wait before reporting MongoDB as unavailable |

If your MongoDB needs a username and password, put them only in the git-ignored `.env`. Never commit them or put them in documentation.

## 8. Local MongoDB setup (Windows 11, no Docker)

1. Download **MongoDB Community Server** for Windows from https://www.mongodb.com/try/download/community and run the MSI installer. Choose to run it as a Windows Service (the default); the default service name is `MongoDB`.
2. Check it is running in PowerShell: `Get-Service MongoDB` should show `Running`. If not, start it from an administrator PowerShell: `Start-Service MongoDB`.
3. The defaults match `.env.example`, so `Copy-Item .env.example .env` needs no changes for a local, unauthenticated instance.
4. Optional tools: MongoDB Compass (graphical browser) and `mongosh` (shell) from the same download site.

## 9. Seed script (development only)

`scripts/seed_database.py` inserts 8 events, 3 rules and 2 alerts, all clearly synthetic (`test_user`, `demo_user`, `192.168.1.20`, `192.168.1.30`, event metadata `synthetic: true`, descriptions starting with `[Synthetic seed]`). It is never run by the application. It skips records that already exist, deletes nothing, and refuses to run when `ENVIRONMENT=production`.

From `backend` with the venv active:

```powershell
python ..\scripts\seed_database.py
```

## 10. Verifying the connection

1. With the backend running, open http://localhost:8000/api/v1/health or run `Invoke-RestMethod http://localhost:8000/api/v1/health`. `"database": "connected"` means MongoDB answered. If MongoDB is down the endpoint still returns HTTP 200 with `"status": "degraded"` and `"database": "unavailable"`, and takes up to the timeout above to answer.
2. After seeding, inspect data with Compass or `mongosh soc_detection_platform --eval "db.security_events.countDocuments()"` (expect 8).
3. Optional tests against the real database, using a throwaway `soc_test_<random>` database that is deleted afterwards:
   ```powershell
   $env:RUN_MONGO_INTEGRATION = "1"; python -m pytest tests/test_mongo_integration.py
   ```

## 11. Decisions and differences from Step 2

| Topic | Decision |
| --- | --- |
| Collection names | `security_events`, `alerts`, `detection_rules`, `investigations`. These replace the provisional `events`/`rules` names used in Step 2 |
| Event fields | Step 3 stores the 11 fields requested. Step 2's extra optional fields (`destination_ip`, `destination_port`, `http_status`, `url_path`, `failure_reason`, ...) can be kept in `metadata` for now. They should become first-class fields in Step 4, when the normalisers need them, with matching indexes. `event_id` is supplied by the caller here, and `created_at` takes the place of `ingested_at` |
| Rule shape | Rules use a free-form `conditions` object, as requested. Step 2's `rule_type` / `filter` / `group_by` / `parameters` layout can live inside `conditions`, or be promoted to top-level fields, when the engine is built. `detection-strategy.md` still shows the Step 2 layout |
| Investigation status | The spec gave only `open`. `open`, `in_progress`, `closed` is an assumption and easy to change |
| Health status | `degraded` is returned with HTTP 200 so the frontend keeps working and can show the state |

## 12. Known limitations

- Tests use an in-memory stand-in (mongomock), which does not behave identically to a real server. The optional integration test covers the real-server paths and must be run on a machine with MongoDB.
- `update` reads then writes, so concurrent updates to the same record follow last-write-wins.
- `/health` waits for the timeout when MongoDB is down.
- No data retention, backup or authentication for MongoDB itself is configured. This is a local development setup.
