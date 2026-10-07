# Log Parsing (Step 5)

This step lets the platform accept **raw log lines** in several formats and turn them into the normalized security events from Step 4. It does **not** detect anything: there are no rules, thresholds, correlation or alerts here.

Related: [event-ingestion.md](event-ingestion.md), [event-normalization.md](event-normalization.md), [system-architecture.md](system-architecture.md).

## 1. Why a parser layer

Real systems log in different shapes: syslog text, web access lines, Windows event JSON, network records. Detection rules (a later step) must not care about those shapes, so each format is converted once, at the edge, into the same event structure. Parsing stays separate from detection: a parser describes *what happened* (a 404 is `failed`, not "malicious"); deciding whether it matters is the detection engine's job.

## 2. Flow

```text
Raw log (text or JSON)
        |
        v
POST /api/v1/events/parse[/batch]      api/v1/parsing.py       HTTP only
        |
        v
ParsingService                         services/parsing_service.py
   |  1. registry.get_parser(source_type)
   |  2. parser.parse(raw_log)  -> dict of event fields       parsers/*.py
   |  3. EventCreate.model_validate(dict)  -> normalization + validation (Step 4 rules)
   |  4. EventIngestionService.ingest_event / ingest_many     (Step 4)
        |
        v
MongoDB  security_events
```

No new event model, repository or ingestion service was added: parsers feed the existing `EventCreate`, so the Step 4 normalization (aliases, case, timestamps in UTC, IP validation, credential-key rejection) applies to parsed events exactly as to JSON events.

## 3. Parser architecture

```text
backend/app/parsers/
  base.py                 BaseParser (abstract), ParseError, shared helpers
  linux_auth_parser.py    LinuxAuthParser      source_type "linux_auth"
  web_log_parser.py       WebLogParser         source_type "web_application"
  windows_event_parser.py WindowsEventParser   source_type "windows_event"
  network_log_parser.py   NetworkLogParser     source_type "network"
  registry.py             ParserRegistry, default_registry(), UnsupportedParserError
```

Every parser implements `parse(raw_log) -> dict` and raises `ParseError(code, message, field=None)` when it cannot. Parsers are stateless, never touch the database and never include the raw log in error messages (it may contain sensitive data).

**Adding a format:** subclass `BaseParser`, set `source_type` (a `SourceType` value), and add the instance to `default_registry()`. No existing parser changes.

## 4. Registry

`ParserRegistry` is a dict from source type to parser instance. Lookup canonicalizes the name with the same function used for event sources (`Linux-Auth`, `windows` and `web` work). An unknown type raises `UnsupportedParserError`, which carries the list of supported types.

## 5. Supported formats

| `source_type` | Input | Recognized |
| --- | --- | --- |
| `linux_auth` | syslog text | `Failed <method> for [invalid user] U from IP`, `Accepted <method> for U from IP`, `Invalid user U from IP`, `User U from IP not allowed because ...` (blocked), `refused connect from H (IP)` (blocked), PAM `authentication failure; ... rhost= user=` |
| `web_application` | Common Log Format, optionally Combined | `IP - - [DD/Mon/YYYY:HH:MM:SS +ZZZZ] "METHOD /path HTTP/x" status size` |
| `windows_event` | JSON object (or string) | `EventID` 4624 (success) and 4625 (failed) |
| `network` | JSON object (or string), or one CSV line | source/destination IP and port, protocol, action, status |

CSV column order: `timestamp,source_ip,destination_ip,source_port,destination_port,protocol,action,status`. Required network fields: `source_ip`, `destination_ip`, `destination_port`, `protocol`.

### Mapping summary

| Format | `event_type` | `action` | `status` |
| --- | --- | --- | --- |
| Linux auth | `authentication` | `login` | `failed`, `success` or `blocked` |
| Web | `web` | `http_request` | `failed` for HTTP >= 400, otherwise `success` |
| Windows | `authentication` | `login` | 4624 `success`, 4625 `failed` |
| Network | `network` | from log, default `connection` | allow/accept/permit -> `success`; deny/drop/reject/block -> `blocked`; unrecognized or missing -> `unknown` |

Source-specific details go in `metadata` (for example `method`, `path`, `http_status`, `response_size`, `event_id`, `computer`, `destination_port`, `protocol`, `auth_method`, `reason`, `hostname`, `pid`). Passwords and credentials are never stored; the event schema also rejects credential-like metadata keys.

## 6. Timestamps

- **Syslog** has no year or time zone. The parser uses the most recent past occurrence of that month/day and assumes UTC, and marks the event with `timestamp_year_assumed: true` and `timezone_assumed: "UTC"`. RFC 3339 syslog timestamps are used as given.
- **Web** timestamps carry an offset and are converted to UTC.
- **Windows/network** use the supplied ISO 8601 value. If it is missing, the event is stored with the ingestion time and Step 4 marks it `timestamp_generated: true`.

## 7. Error handling

| Situation | Single endpoint | Batch endpoint |
| --- | --- | --- |
| Unknown `source_type` | `400`, code `unsupported_source_type`, lists supported types | `400` for the whole request |
| Log cannot be parsed | `422`, `{"error": {"message", "code", "field"?}}` | that item is listed in `errors` (with `index`) |
| Parsed data fails event validation | `422`, code `validation_failed`, `details` per field | item listed in `errors` with `details` |
| Malformed request body | `422` (standard validation error) | `422` |
| MongoDB unavailable | `503 {"error": {"message": "Database is unavailable"}}` | `503` |

Error codes: `invalid_log`, `unsupported_event`, `missing_field`, `invalid_field`, `validation_failed`, `parser_error`. Optional fields that are absent are simply left out; nothing is invented. Responses never contain stack traces, connection strings or the submitted log text.

In a batch, each log is handled on its own. Valid logs are stored in one insert; the response is `201` if at least one log was accepted and `422` if all were rejected (same rule as `POST /events/batch`). Limit: 500 logs per request.

## 8. Endpoints

### `POST /api/v1/events/parse`

```json
{"source_type": "linux_auth", "raw_log": "Oct  2 10:15:23 server sshd[1234]: Failed password for test_user from 192.168.1.20 port 54321 ssh2"}
```

`201`:

```json
{
  "success": true,
  "message": "Log parsed and security event ingested successfully",
  "event": {
    "event_id": "evt_2a22a91be3177732",
    "timestamp": "2026-10-02T10:15:23Z",
    "source": "linux_auth",
    "event_type": "authentication",
    "action": "login",
    "status": "failed",
    "username": "test_user",
    "source_ip": "192.168.1.20",
    "message": "Failed password for test_user from 192.168.1.20 port 54321 ssh2",
    "metadata": {"hostname": "server", "process": "sshd", "auth_method": "password", "pid": 1234, "source_port": 54321,
                 "timestamp_year_assumed": true, "timezone_assumed": "UTC"},
    "created_at": "2026-10-03T11:13:59.257Z"
  }
}
```

`422` for an unparseable log:

```json
{"error": {"message": "Line is not in syslog format (expected 'Mon DD HH:MM:SS host process[pid]: message')", "code": "invalid_log"}}
```

### `POST /api/v1/events/parse/batch`

```json
{"source_type": "linux_auth", "logs": ["<line 1>", "this is not a valid authentication log"]}
```

```json
{
  "success": false, "message": "1 log ingested, 1 rejected",
  "total": 2, "accepted": 1, "rejected": 1,
  "event_ids": ["evt_..."],
  "errors": [{"index": 1, "code": "invalid_log", "message": "Line is not in syslog format (...)", "field": null, "details": []}]
}
```

## 9. Sample logs and PowerShell checks

Synthetic samples (private IPs, no real data) are in `sample_logs/raw/`: `linux_auth.log`, `web_access.log`, `windows_events.json`, `network_events.json`.

```powershell
# Linux
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/events/parse" -Method POST -ContentType "application/json" `
  -Body '{"source_type":"linux_auth","raw_log":"Oct  2 10:15:23 server sshd[1234]: Failed password for test_user from 192.168.1.20 port 54321 ssh2"}'

# Web
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/events/parse" -Method POST -ContentType "application/json" `
  -Body '{"source_type":"web_application","raw_log":"192.168.1.20 - - [02/Oct/2026:10:20:10 +0000] \"GET /admin HTTP/1.1\" 404 512"}'

# Windows
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/events/parse" -Method POST -ContentType "application/json" `
  -Body '{"source_type":"windows_event","raw_log":{"EventID":4625,"TimeCreated":"2026-10-02T10:25:00Z","Computer":"WIN-SERVER","TargetUserName":"test_user","IpAddress":"192.168.1.20","Message":"An account failed to log on."}}'

# Network
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/events/parse" -Method POST -ContentType "application/json" `
  -Body '{"source_type":"network","raw_log":{"timestamp":"2026-10-02T10:30:00Z","source_ip":"192.168.1.20","destination_ip":"192.168.1.10","source_port":54321,"destination_port":22,"protocol":"TCP","action":"connection","status":"allowed"}}'
```

Load a whole sample file in a batch (PowerShell):

```powershell
$logs = Get-Content "..\sample_logs\raw\linux_auth.log"
$body = @{ source_type = "linux_auth"; logs = @($logs) } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/events/parse/batch" -Method POST -ContentType "application/json" -Body $body
```

## 10. Limitations

- Only the patterns in section 5 are recognized; other lines are rejected with `unsupported_event` or `invalid_log`, not guessed.
- Syslog year and time zone are assumptions (flagged in metadata).
- Web `path` keeps the query string as logged, so it may contain sensitive values; use synthetic or authorized data only.
- One log record per call item; multi-line records and file upload are not supported.
- No authentication yet, as in Step 4.
