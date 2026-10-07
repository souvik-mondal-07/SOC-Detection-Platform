# Event Ingestion (Step 4)

This step makes the platform accept security events, validate and normalize them, and store them in MongoDB. It does **not** detect anything: there are no rules, thresholds or alerts here.

Related: [event-normalization.md](event-normalization.md), [database.md](database.md), [system-architecture.md](system-architecture.md).

## 1. Event lifecycle

```text
Incoming JSON
     |
     v
POST /api/v1/events (or /events/batch)       api/v1/events.py        translates HTTP to a service call
     |
     v
Validation + normalization                   models/event.py         EventCreate; rules in models/normalization.py
     |
     v
Build stored event                           services/ingestion_service.py
   - generate event_id (evt_ + 16 random hex characters)
   - set created_at (UTC)
   - use ingestion time if no timestamp was sent
     |
     v
EventRepository.create_event / create_many  repositories/event_repository.py
     |
     v
MongoDB: security_events
```

Reading goes `GET /events` -> `EventIngestionService` -> `EventRepository.get_events` -> MongoDB.

**Separation rule.** The route and the ingestion service import nothing about rules, alerts or investigations, and the routes contain no database calls. A test enforces both. The future detection engine will read events that are already stored and will be a separate module:

```text
Log/File/API -> Ingestion -> Normalization -> MongoDB -> Detection Engine -> Alert Engine -> Dashboard
                 (Step 4)     (Step 4)         (Steps 3-4)   (later)           (later)         (later)
```

## 2. Endpoints

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| POST | `/api/v1/events` | Ingest one event | 201 |
| POST | `/api/v1/events/batch` | Ingest up to 500 events | 201 (422 if none accepted) |
| GET | `/api/v1/events` | Recent events, newest first | 200 |
| GET | `/api/v1/events/{event_id}` | One event | 200 (404 if unknown) |

Interactive docs are at http://localhost:8000/docs while the backend runs.

### Incoming event (request body)

| Field | Required | Notes |
| --- | --- | --- |
| `source` | yes | `linux_auth`, `windows_event`, `web_application`, `network`, `application` |
| `event_type` | yes | `authentication`, `web`, `network`, `privilege`, `system`, `application` |
| `action` | yes | For example `login`, `connection`, `privilege_change` |
| `message` | yes | 1 to 1000 characters |
| `timestamp` | no | ISO 8601 with timezone. Generated if missing |
| `status` | no | `success`, `failed`, `blocked`, `unknown` (default `unknown`) |
| `username` | no | Up to 64 characters |
| `source_ip` | no | IPv4 or IPv6 |
| `metadata` | no | Free-form object (see limits in the normalization doc) |

Values are normalized first, so `"status": "FAILED"` is accepted. `event_id` and `created_at` cannot be sent.

### Stored event (response)

`event_id`, `timestamp`, `source`, `event_type`, `action`, `status`, `username`, `source_ip`, `message`, `metadata`, `created_at`. MongoDB's internal `_id` is never returned. Optional fields that were not sent are returned as `null`. The POST response includes the full event, a superset of the short example in the brief.

### GET /events query parameters

| Parameter | Meaning |
| --- | --- |
| `limit` | 1 to 500, default 50 |
| `source`, `event_type`, `status` | Exact match. Normalized like incoming values (`status=FAILED` works) |
| `source_ip` | Exact match on a valid IP address |

Filters combine with AND. Unknown parameters and invalid values return 422. There is no paging or free-text search yet.

## 3. Sample requests and responses

All responses below were produced by running the real API.

**Create an event** `POST /api/v1/events` -> `201 Created`

```json
{
  "success": true,
  "message": "Security event ingested successfully",
  "event": {
    "event_id": "evt_24c1c5f6e865f497",
    "timestamp": "2026-10-02T10:15:23Z",
    "source": "linux_auth",
    "event_type": "authentication",
    "action": "login",
    "status": "failed",
    "username": "test_user",
    "source_ip": "192.168.1.20",
    "message": "Failed password for test_user",
    "metadata": {},
    "created_at": "2026-10-02T18:10:02.562000Z"
  }
}
```

**Validation error** `422 Unprocessable Entity` (sent: `"timestamp": "not-a-date"`, `"event_type": "banana"`)

```json
{
  "error": {
    "message": "Validation failed",
    "details": [
      {"field": "body.timestamp", "message": "Value error, timestamp must be an ISO 8601 date-time with a timezone, e.g. 2026-10-02T10:15:23Z"},
      {"field": "body.event_type", "message": "Input should be 'authentication', 'web', 'network', 'privilege', 'system' or 'application'"}
    ]
  }
}
```

**Batch, mixed result** `POST /api/v1/events/batch` -> `201 Created`

```json
{
  "success": false,
  "message": "1 event ingested, 1 rejected",
  "accepted": 1,
  "rejected": 1,
  "event_ids": ["evt_17d1379ee1d9e1d1"],
  "errors": [
    {"index": 1, "errors": [{"field": "source", "message": "Input should be 'linux_auth', 'windows_event', 'web_application', 'network' or 'application'"}]}
  ]
}
```

**Not found** `GET /api/v1/events/evt_doesnotexist` -> `404 Not Found`

```json
{"error": {"message": "Event not found"}}
```

## 4. Batch behavior

- Each event is validated on its own. **Valid events are stored even if others are rejected.**
- `accepted`, `rejected`, `event_ids` (accepted events, in submission order) and `errors` (one entry per rejected event, with its 0-based `index`) are always returned.
- HTTP **201** if at least one event was stored. HTTP **422** if none were, and nothing is stored. `success` is `true` only when every event was accepted, so check `rejected` or `errors` as well as the status code.
- Items that are not JSON objects are rejected individually. An empty list, a non-list, or more than 500 events rejects the whole request with 422.

## 5. Error behavior

| Situation | Status | Body |
| --- | --- | --- |
| Invalid, missing or unknown fields; bad timestamp, enum or IP; bad query parameter; malformed JSON | 422 | `error.message` plus `error.details` (field and message only) |
| Unknown event ID | 404 | `error.message` |
| MongoDB unreachable | 503 | `{"error": {"message": "Database is unavailable"}}` |
| Duplicate ID (should not happen with generated IDs) | 409 | `{"error": {"message": "Record already exists"}}` |
| Anything unexpected | 500 | `{"error": {"message": "Internal server error"}}` |

Responses never contain connection strings, stack traces, file paths, or the values you sent. The details are limited to field names and messages, so a secret in a rejected request is not echoed back.

## 6. Test the API from PowerShell

Start the backend first (from `backend`, venv active, MongoDB running):

```powershell
uvicorn app.main:app --reload --port 8000
```

In a second PowerShell window, from the `backend` folder. The commands use only `Invoke-RestMethod`.

**1. Insert one event**

```powershell
$base = "http://localhost:8000/api/v1"

$body = @{
    timestamp  = "2026-10-02T10:15:23Z"
    source     = "linux_auth"
    event_type = "authentication"
    action     = "login"
    status     = "failed"
    username   = "test_user"
    source_ip  = "192.168.1.20"
    message    = "Failed password for test_user"
    metadata   = @{}
} | ConvertTo-Json -Depth 5

$created = Invoke-RestMethod -Method Post -Uri "$base/events" -ContentType "application/json" -Body $body
$created | ConvertTo-Json -Depth 5
$id = $created.event.event_id
```

**2. Retrieve events**

```powershell
(Invoke-RestMethod -Uri "$base/events?limit=20").events |
    Format-Table event_id, timestamp, source, event_type, status, username, source_ip
```

**3. Retrieve one event**

```powershell
Invoke-RestMethod -Uri "$base/events/$id" | ConvertTo-Json -Depth 5
```

**4. Filter events**

```powershell
(Invoke-RestMethod -Uri "$base/events?event_type=authentication&status=failed&limit=20").events |
    Format-Table event_id, timestamp, status, username, source_ip
```

**5. Insert batch events from the sample files**

```powershell
foreach ($name in "normal_auth", "failed_auth", "web_events", "network_events") {
    $events = Get-Content "..\sample_logs\$name.json" -Raw | ConvertFrom-Json
    $batch  = @{ events = @($events) } | ConvertTo-Json -Depth 10
    $result = Invoke-RestMethod -Method Post -Uri "$base/events/batch" -ContentType "application/json" -Body $batch
    "{0}: accepted={1} rejected={2}" -f $name, $result.accepted, $result.rejected
}
```

**6. See a validation error**

```powershell
try {
    Invoke-RestMethod -Method Post -Uri "$base/events" -ContentType "application/json" `
        -Body '{"timestamp":"not-a-date","source":"linux_auth","event_type":"banana","action":"login","message":"x"}'
} catch {
    $_.ErrorDetails.Message
}
```

**7. See a 404**

```powershell
try { Invoke-RestMethod -Uri "$base/events/evt_doesnotexist" } catch { $_.ErrorDetails.Message }
```

Running these twice stores the events twice (each gets a new ID). To start clean during development, delete the database in MongoDB Compass; the application never deletes data itself.

## 7. Sample files

`sample_logs/` holds small synthetic datasets, each a JSON array that can be sent to `/events/batch`.

| File | Events | Content |
| --- | --- | --- |
| `normal_auth.json` | 6 | Ordinary logins and logout, one single mistyped password |
| `failed_auth.json` | 9 | Repeated failed logins and invalid-user attempts from one address, then a success |
| `web_events.json` | 6 | Page requests with 200, 404, 403 and 401 responses (HTTP details in `metadata`) |
| `network_events.json` | 7 | Allowed and firewall-blocked connections (ports in `metadata`) |

All data is synthetic: accounts `test_user`, `demo_user`, `unknown_user_1`, `unknown_user_2`, only private `192.168.1.x` addresses, and `metadata.synthetic = true`. A test checks this. The files contain patterns that later detection rules may flag, but nothing in this step does.

## 8. Limits

| Limit | Value |
| --- | --- |
| Events per batch | 500 |
| `message` length | 1000 characters |
| `metadata` size / depth | 10,000 characters as JSON / 8 levels |
| `GET /events` page size | 500 (default 50) |

## 9. Security notes and limitations

- **No authentication yet.** Anyone who can reach the API can submit and read events. Run it only on a local machine or a trusted lab network, and use only synthetic or authorized data. uvicorn listens on 127.0.0.1 by default.
- **CORS** now allows `GET` and `POST` from the local frontend origin. CORS only restricts browsers, not tools like PowerShell.
- Submitted events can be forged by anyone who reaches the API. Nothing yet verifies that an event really came from its claimed source.
- No de-duplication: sending the same event twice stores two events.
- Credential-like **keys** in `metadata` are rejected, but free text in `message` is not scanned. Do not send real secrets.
- A batch is stored with a single unordered insert; if MongoDB fails part-way the request returns 503 and some events may already be stored.
- Streaming, file upload and real log collection are not implemented. Parsing other log formats is Step 5.
