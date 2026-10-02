# System Architecture

**Status:** design only (Step 2). Nothing described as "planned" here is implemented yet.
Research background and the project gap are in [`../research.md`](../research.md). Rules, alert lifecycle, severity and evaluation are in [`detection-strategy.md`](detection-strategy.md).

## 1. Problem statement

Security systems generate large numbers of events and logs. Without appropriate detection rules and correlation mechanisms, suspicious patterns can be hard to identify quickly. Examples are repeated authentication failures, suspicious login sequences, excessive HTTP errors, port-scanning patterns and privilege-related activity.

The MVP is a lightweight platform that:

- accepts authorised security-event data,
- normalises events into one format,
- applies configurable detection rules,
- identifies suspicious activity,
- generates severity-based alerts, and
- provides one interface for monitoring and investigation.

It is **not** a replacement for enterprise SIEM platforms. It is an educational and practical detection-engineering platform that demonstrates core SOC concepts.

## 2. Objectives

| # | Objective | How it will be checked |
| --- | --- | --- |
| 1 | Ingest events from authorised synthetic sources: Linux-style auth logs, web access logs, network connection records and privilege/admin audit records | Sample files for all four source types load without error |
| 2 | Normalise those four formats into the single event model in section 6 | Unit tests parse sample lines into expected normalised events |
| 3 | Build a rule-based detection engine driven by rule definitions, with no per-rule code | A new threshold rule can be added by adding data only |
| 4 | Detect the 11 initial rule patterns in `detection-strategy.md` across 5 categories | Each rule has a passing test using a small hand-made event set |
| 5 | Create alerts with a severity from the documented criteria (LOW to CRITICAL) | Each alert stores rule, severity, matched events and time range |
| 6 | Provide a dashboard showing alerts, events and rules | Dashboard pages replace the Step 1 placeholders |
| 7 | Let an analyst open an alert, see its related events and change its status | Alert detail view and status-change flow |
| 8 | Measure detection effectiveness on labelled synthetic datasets | Metrics defined in `detection-strategy.md` section 10, reported only after real runs |
| 9 | Keep the design extensible | New rule types and event sources added without changing existing modules beyond a registry entry |

## 3. Scope

### In scope

- Authentication, web/application, basic network and privilege-related events
- Rule-based detection and event correlation
- Alert generation, severity classification and alert investigation
- Event search and filtering
- Synthetic security datasets, detection testing and performance evaluation

### Out of scope for the MVP

- Real malware execution
- Exploitation of real systems
- Offensive attack automation
- Full enterprise SIEM functionality
- Autonomous incident response
- Production-scale distributed architecture
- Real-world personal data
- Unauthorised monitoring

### Authorised-environment requirement

The platform may only process data that is **synthetic** or comes from systems the operator owns or has **written permission** to monitor. Concretely:

1. Sample datasets are generated for this project. They use fictional usernames and addresses from reserved documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and private lab ranges.
2. No real credentials, personal data or third-party log data are loaded.
3. The platform only reads data given to it. It performs no scanning or probing of any network or host.
4. Dataset generators write log lines only. They do not send traffic.

## 4. High-level architecture

```text
                    ┌─────────────────────┐
                    │    Security Logs    │
                    │  / Sample Events    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Log Ingestion     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Parser & Normalizer │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Detection Engine   │
                    │                     │
                    │  Configurable Rules │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 No Match              Match
                    │                     │
                    ▼                     ▼
                 Continue           Alert Engine
                                          │
                                          ▼
                                  ┌───────────────┐
                                  │    MongoDB    │
                                  └───────┬───────┘
                                          │
                                          ▼
                                  ┌───────────────┐
                                  │ SOC Dashboard │
                                  └───────────────┘
```

**Design note on persistence.** The diagram shows alerts flowing into MongoDB. Investigation needs the underlying events too, so the design also stores every **normalised event** (before detection runs). The "No Match -> Continue" path therefore still keeps the event. Collections as implemented in Step 3: `security_events`, `alerts`, `detection_rules` and `investigations` (see [database.md](database.md)).

### Component responsibilities

| Component | Responsibility | Does not do |
| --- | --- | --- |
| Security logs / sample events | Source data: synthetic files in four formats (section 6.1) | Hold real data |
| Log ingestion | Accept raw records (file or API upload), tag them with a source type, hand them to the normaliser, report counts of accepted and rejected records | Interpret record contents |
| Parser & normaliser | Turn each source-specific record into the common event model, validate fields, convert timestamps to UTC, reject malformed records with a reason | Decide whether an event is suspicious |
| Detection engine | Load enabled rules, evaluate events against them, keep per-rule time-window state, emit match results | Create or store alerts, know about the database |
| Alert engine | Turn match results into alerts: apply severity, de-duplicate, attach matched event IDs, set initial status | Evaluate rules |
| MongoDB | Persist events, alerts and rules | Hold business logic |
| API layer | Expose events, alerts, rules and investigation actions over HTTP | Contain detection logic |
| SOC dashboard | Show alerts, events and rules; support filtering and the investigation workflow | Perform detection |

### Key flows

1. **Ingest and detect (batch first).** Upload -> parse and normalise -> store events -> run enabled rules over the batch in timestamp order -> create alerts -> store alerts.
2. **Investigate.** Dashboard opens an alert -> API returns the alert and its matched events -> analyst changes status and adds a note.
3. **Rule management.** Dashboard lists rules -> analyst enables or disables a rule or edits its parameters.

Real-time or streaming ingestion is out of scope for the early steps. Batch processing comes first, and the detection engine is designed so that streaming can be added later (decision AD-5).

## 5. Backend architecture

### 5.1 Current state (Step 1, implemented)

```text
backend/app/
├── main.py              App factory, CORS, error handlers
├── api/
│   ├── router.py        Collects versioned routers
│   └── v1/health.py     GET /api/v1/health
├── core/
│   ├── config.py        Environment-based settings
│   └── errors.py        Uniform JSON errors
├── services/            (empty package)
├── models/              (empty package)
└── repositories/        (empty package)
```

*Step 3 update: `core/database.py`, the four models, the repositories and database initialization now exist. See [database.md](database.md).*

### 5.2 Planned modules (not created yet)

Layering rule, unchanged from Step 1: `api` -> `services` -> `repositories`. Only repositories touch the database.

```text
backend/app/
├── api/v1/
│   ├── events.py            Ingest and query events
│   ├── alerts.py            List alerts, change status
│   ├── rules.py             List and update rules
│   └── investigations.py    Alert detail, related events, notes
├── core/
│   ├── database.py          MongoDB connection (Step 3)
│   └── security.py          Authentication helpers (later step)
├── models/
│   ├── event.py             Event schema
│   ├── alert.py             Alert schema and status enum
│   └── rule.py              Rule schema
├── services/
│   ├── ingestion_service.py
│   ├── normalization_service.py   Dispatches to per-source parsers
│   ├── detection_service.py       Loads rules, runs evaluators
│   ├── alert_service.py           Creates and updates alerts
│   ├── parsers/                   One small module per source type
│   └── detection/evaluators/      One module per rule type
└── repositories/
    ├── event_repository.py
    ├── alert_repository.py
    └── rule_repository.py
```

Supporting folders to be added when needed: `backend/rules/` (default rule definitions as JSON) and a dataset generator under `scripts/`.

### 5.3 Planned API (illustrative, not final)

| Method | Path | Purpose | State |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | Service health | **Implemented** |
| POST | `/api/v1/events/ingest` | Upload raw records for a given source type | Planned |
| GET | `/api/v1/events` | Search and filter events | Planned |
| GET | `/api/v1/rules` | List rules | Planned |
| PATCH | `/api/v1/rules/{rule_id}` | Enable/disable, adjust parameters | Planned |
| GET | `/api/v1/alerts` | List and filter alerts | Planned |
| GET | `/api/v1/alerts/{alert_id}` | Alert detail with matched events | Planned |
| PATCH | `/api/v1/alerts/{alert_id}/status` | Change alert status | Planned |

### 5.4 Frontend mapping

| Sidebar item (exists in Step 1) | Backend area |
| --- | --- |
| Overview | Alert and event summaries |
| Security Events | `events` |
| Alerts | `alerts` |
| Detection Rules | `rules` |
| Investigations | `investigations` |
| Settings | Configuration (later) |

## 6. Normalised security-event model

All sources are converted to one format before detection, so rules are written once, not once per log format.

```json
{
  "timestamp": "2026-10-02T10:15:23Z",
  "source": "linux_auth",
  "event_type": "authentication",
  "action": "login",
  "status": "failed",
  "username": "test_user",
  "source_ip": "192.0.2.20",
  "failure_reason": "bad_password",
  "message": "Failed password for test_user",
  "metadata": {}
}
```

### 6.1 Field reference

**Required on every event**

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | ISO 8601 string, UTC | When the event happened (event time, not arrival time) |
| `source` | string | Origin format: `linux_auth`, `web_access`, `network_conn`, `audit_log` |
| `event_type` | enum | `authentication`, `web`, `network`, `privilege` |
| `action` | string | What was done, e.g. `login`, `http_request`, `connection`, `privilege_change`, `admin_action` |
| `status` | enum | `success`, `failed`, `unknown`. Web: 2xx/3xx = `success`, 4xx/5xx = `failed`. Network: blocked or refused = `failed` |
| `message` | string | Human-readable summary or the original line |

**Optional (filled when the source provides them)**

| Field | Used by | Meaning |
| --- | --- | --- |
| `username` | auth, privilege | Account performing the action (synthetic) |
| `target_user` | privilege | Account affected by a privilege change |
| `source_ip` | auth, web, network | Originating address (synthetic) |
| `destination_ip` | network | Target address |
| `destination_port` | network | Target port, 0-65535 |
| `protocol` | network | e.g. `tcp`, `udp` |
| `http_method` | web | e.g. `GET`, `POST` |
| `url_path` | web | Requested path |
| `http_status` | web | HTTP status code |
| `user_agent` | web | Client string (synthetic) |
| `failure_reason` | auth | e.g. `bad_password`, `invalid_user` |
| `hostname` | any | Synthetic host name |
| `metadata` | any | Free-form object for source-specific extras that are not normalised |

**Assigned by the system (not supplied by the source)**

| Field | Meaning |
| --- | --- |
| `event_id` | Unique ID, assigned at ingestion |
| `ingested_at` | When the platform received the event |
| `raw` | Original record text, kept for investigation |

Ground-truth labels for evaluation are stored in separate files, never inside events, so detection cannot see them.

### 6.2 Example events (all synthetic)

```json
{"timestamp":"2026-10-02T10:20:01Z","source":"web_access","event_type":"web","action":"http_request","status":"failed","source_ip":"198.51.100.7","http_method":"GET","url_path":"/missing-page","http_status":404,"message":"GET /missing-page 404","metadata":{}}
{"timestamp":"2026-10-02T10:21:10Z","source":"network_conn","event_type":"network","action":"connection","status":"failed","source_ip":"203.0.113.9","destination_ip":"10.0.0.5","destination_port":2222,"protocol":"tcp","message":"Connection refused","metadata":{}}
{"timestamp":"2026-10-02T10:30:44Z","source":"audit_log","event_type":"privilege","action":"privilege_change","status":"success","username":"test_admin","target_user":"test_user","message":"Role changed to admin","metadata":{}}
```

## 7. Architecture decisions

| ID | Decision | Reason |
| --- | --- | --- |
| AD-1 | **Rules are data.** A small fixed set of rule types (`match`, `threshold`, `distinct_count`, `sequence`) is implemented in code. Individual rules are JSON that configure those types. | New rules need no change to the engine. A new rule *type* needs one new evaluator module |
| AD-2 | **Normalise before detecting.** Detection only sees the common event model | One rule works across sources; parsers stay isolated |
| AD-3 | **Persist events as well as alerts** | Investigation requires the underlying events |
| AD-4 | **Keep the `api` -> `services` -> `repositories` layering** | Already established in Step 1; lets MongoDB be added without touching logic |
| AD-5 | **Batch first, streaming later.** The detection engine takes an ordered list of events and returns matches, with no I/O inside | Easy to unit test and to measure; can be fed by a stream later |
| AD-6 | **Keep the versioned `/api/v1` structure.** New routers go under `api/v1/` rather than directly under `api/` | Step 1 already works this way; avoids changing working code |
| AD-7 | **Event-time windows in UTC** | Results do not depend on when the batch is processed |
| AD-8 | **One alert per rule, group key and window**, not one per event | Prevents alert floods; behaviour is tested in evaluation |
| AD-9 | **MongoDB for storage** (integrated in Step 3) | Document model suits events whose optional fields differ by source; SQL databases are excluded by project constraints |
| AD-10 | **Synthetic data only** | Authorised-environment requirement (section 3) |

## 8. Known risks and open questions

- Threshold values are starting points. They will be tuned against synthetic datasets, and tuned values only reflect those datasets.
- Behind shared addresses (NAT, proxies) a source IP may represent many users. The MVP treats the IP as given.
- Out-of-order or late events can affect window rules. The MVP processes batches sorted by event time.
- Collection design, indexes and retention are Step 3 decisions.
