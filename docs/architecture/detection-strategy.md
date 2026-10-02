# Detection Strategy

**Status:** design only (Step 2). No rule, alert or evaluation code exists yet, and **no results have been measured**.
Context: [`system-architecture.md`](system-architecture.md). Research: [`../research.md`](../research.md).

## 1. Principles

- **Rules are data.** Each rule is a JSON document that configures one of a small set of rule types.
- **Explainable.** Every alert states which rule fired, which events matched and why.
- **Deterministic.** The same events and rules always produce the same alerts, which is what makes testing and evaluation possible.
- **Tunable.** Thresholds, windows and severities are parameters, not code.
- **Scoped to the MVP.** The rules look for patterns in log events from authorised environments. They are simple on purpose.

## 2. Rule types

| Type | Meaning | Example use |
| --- | --- | --- |
| `match` | A single event satisfies the filter | A privilege change occurred |
| `threshold` | At least N events satisfying the filter, for the same group key, within a time window | 5 failed logins from one IP in 5 minutes |
| `distinct_count` | At least N different values of a field, for the same group key, within a window | One IP contacting 15 different ports in 2 minutes |
| `sequence` | Ordered stages, each with its own filter and optional count, for the same key, within a window | 5 failed logins followed by a success |

Adding a **rule** only means adding data. Adding a **rule type** means adding one evaluator module and registering it (see section 6).

## 3. Rule structure

### 3.1 Schema

```json
{
  "rule_id": "AUTH-001",
  "name": "Multiple Failed Logins",
  "category": "authentication",
  "description": "Detect repeated failed authentication attempts from one source",
  "severity": "high",
  "enabled": true,
  "rule_type": "threshold",
  "filter": {
    "event_type": "authentication",
    "action": "login",
    "status": "failed"
  },
  "group_by": ["source_ip"],
  "parameters": {
    "threshold": 5,
    "window_minutes": 5
  }
}
```

| Field | Meaning |
| --- | --- |
| `rule_id` | Unique ID: category prefix + number (`AUTH`, `WEB`, `NET`, `PRIV`, `COR`) |
| `name`, `description` | Human-readable text shown in the dashboard and in alerts |
| `category` | `authentication`, `web`, `network`, `privilege`, `correlation` |
| `severity` | Default severity: `low`, `medium`, `high`, `critical` (section 8) |
| `enabled` | Disabled rules are skipped |
| `rule_type` | One of the types in section 2 |
| `filter` | Field conditions an event must satisfy. A value can be a single value, a list (any of), or an operator object such as `{"not_in": [...]}` or `{"contains_any": [...]}` |
| `group_by` | Fields that define "the same entity" for counting, e.g. `["source_ip"]`. Empty for `match` rules |
| `parameters` | Type-specific values: `threshold`, `window_minutes`, `distinct_field`, or for `sequence` a `stages` list |

**Difference from the brief's example.** The brief placed `threshold` and `window_minutes` inside `conditions`. This design separates *which events count* (`filter`) from *how they are counted* (`parameters`, `group_by`). That keeps filters reusable and makes each evaluator's inputs explicit. The fields in the brief's example are all preserved.

### 3.2 Sequence rule example

```json
{
  "rule_id": "AUTH-002",
  "name": "Successful Login After Repeated Failures",
  "category": "authentication",
  "severity": "critical",
  "enabled": true,
  "rule_type": "sequence",
  "group_by": ["source_ip", "username"],
  "parameters": {
    "window_minutes": 10,
    "stages": [
      { "filter": { "event_type": "authentication", "action": "login", "status": "failed" }, "min_count": 5 },
      { "filter": { "event_type": "authentication", "action": "login", "status": "success" }, "min_count": 1 }
    ]
  }
}
```

Sequence semantics: all stages must be satisfied in order, with the same group key, and the whole sequence must fall within `window_minutes` of event time.

## 4. Initial rule catalogue

The 11 initial rules. **All numeric parameters are starting values to be tuned against the synthetic datasets. They are not validated and not based on any published standard.** Severities follow section 8.

### Authentication

| ID | Name | Type | Logic | Group by | Start params | Severity |
| --- | --- | --- | --- | --- | --- | --- |
| AUTH-001 | Multiple failed logins | threshold | Failed `login` events | `source_ip` | 5 in 5 min | High |
| AUTH-002 | Successful login after repeated failures | sequence | N failed logins, then a successful login | `source_ip`, `username` | 5 failures then success, 10 min | Critical |
| AUTH-003 | Repeated invalid-user attempts | distinct_count | Failed logins with `failure_reason = invalid_user`, counting distinct `username` | `source_ip` | 3 usernames in 10 min | Medium |

### Web / application

| ID | Name | Type | Logic | Group by | Start params | Severity |
| --- | --- | --- | --- | --- | --- | --- |
| WEB-001 | Excessive 404 responses | threshold | Web events with `http_status = 404` | `source_ip` | 20 in 5 min | Low |
| WEB-002 | Repeated 401/403 responses | threshold | Web events with `http_status` in 401, 403 | `source_ip` | 10 in 5 min | Medium |
| WEB-003 | Suspicious request patterns | match | `url_path` or `user_agent` contains any entry from a configurable indicator list (for example directory-traversal sequences or well-known scanner names) | none | indicator list kept in the rule | Medium |

### Network

| ID | Name | Type | Logic | Group by | Start params | Severity |
| --- | --- | --- | --- | --- | --- | --- |
| NET-001 | Multiple destination ports from one source | distinct_count | Connection events, counting distinct `destination_port` | `source_ip`, `destination_ip` | 15 ports in 2 min | Medium |
| NET-002 | Unusually high connection volume | threshold | Connection events | `source_ip` | 100 in 1 min | Medium |

### Privilege

| ID | Name | Type | Logic | Group by | Start params | Severity |
| --- | --- | --- | --- | --- | --- | --- |
| PRIV-001 | Privilege-change activity | match | `event_type = privilege` and `action` in `privilege_change`, `role_assigned` | none | none | Medium |
| PRIV-002 | Suspicious administrative activity | match | `action = admin_action` by a `username` **not in** an `authorized_admins` list | none | allowlist of synthetic admin names kept in the rule | High |

### Correlation

| ID | Name | Type | Logic | Group by | Start params | Severity |
| --- | --- | --- | --- | --- | --- | --- |
| COR-001 | Authentication followed by privilege activity | sequence | Successful login, then a privilege event by the same `username` | `username` | 15 min | Critical |

**Note on correlation coverage.** The brief lists "multiple failed logins -> successful login" as a correlation. It is implemented once, as AUTH-002 (a sequence rule), so it does not generate duplicate alerts under two IDs. COR-001 covers "authentication -> privilege activity".

**Known false-positive sources to check during evaluation.** WEB-001: broken links and crawlers. NET-002: legitimate bulk transfers. PRIV-001: planned administrator work. AUTH-001: users mistyping passwords, shared NAT addresses.

## 5. Alert generation

For each match, the alert engine creates one alert containing:

- `rule_id`, `rule_name`, `category`
- `severity` (taken from the rule)
- `group_key` (for example `{"source_ip": "198.51.100.7"}`)
- `first_event_time`, `last_event_time`
- `matched_event_ids`
- `status` (initially `open`), `created_at`
- `explanation` (plain-language summary, for example "7 failed logins from 198.51.100.7 within 5 minutes")

**De-duplication (AD-8).** At most one open alert per `rule_id` + `group_key` + window. Further matching events extend the existing alert rather than creating new ones. Exact behaviour is verified in the tests built with the engine.

## 6. Extensibility

**Add a rule** (no engine change): create a JSON document that follows the schema and uses an existing `rule_type`. The rule loader validates it against the schema.

**Add a rule type** (one new module): write an evaluator that implements one interface (events + rule -> matches) and register it under its `rule_type` name in the evaluator registry. The engine looks evaluators up by name and contains no per-rule logic.

**Add an event source**: write a parser module that maps the source format to the event model and register it under its `source` name.

## 7. Alert lifecycle

```text
Event
  ↓
Rule match
  ↓
Alert created
  ↓
Open ──────────────► Investigating ──────────► Resolved
  │                       │
  │                       ▼
  └──────────────► False Positive
```

| Status | Purpose |
| --- | --- |
| **Open** | New alert that no analyst has looked at yet. This is the triage queue |
| **Investigating** | An analyst has taken the alert and is reviewing related events |
| **Resolved** | Review finished and the activity was confirmed as real and handled or understood (a note records the outcome) |
| **False Positive** | Review concluded the activity was benign or the rule fired wrongly. Used as feedback when tuning rules |

**Allowed transitions:** Open -> Investigating, Open -> False Positive, Investigating -> Resolved, Investigating -> False Positive. Resolved and False Positive are final in the MVP, and reopening is out of scope.
**Recorded on every change:** new status, timestamp and an optional analyst note.

**Do not confuse two kinds of "false positive".** The *status* is an analyst's judgement during use. In the *evaluation* (section 10), false positives are decided from the dataset's ground-truth labels.

## 8. Severity levels

Severity expresses the **potential significance of the detected activity within the controlled test environment**. It is not a measure of real-world damage and not a probability that the alert is true.

| Level | Criteria | Typical rules |
| --- | --- | --- |
| **LOW** | Low-confidence or frequently benign signal; no sign of access or impact; suitable for batch review | WEB-001 |
| **MEDIUM** | Pattern consistent with reconnaissance or probing, or a change that needs verification; no sign that access was gained | AUTH-003, WEB-002, WEB-003, NET-001, NET-002, PRIV-001 |
| **HIGH** | Repeated or automated-looking attempts against credentials or access controls, or an administrative action by an account not expected to perform it; needs prompt review | AUTH-001, PRIV-002 |
| **CRITICAL** | Evidence that suspicious activity may have **succeeded**: access gained after repeated failures, or privilege activity following a login | AUTH-002, COR-001 |

**How levels are assigned.** Each rule's severity is set by asking three questions, in this order:

1. **Outcome evidence:** do the events indicate success (a successful login, a privilege change) and not only attempts? Yes -> raise toward CRITICAL.
2. **Target:** does the activity target credentials, access controls or privileged functions? Yes -> at least HIGH when repeated.
3. **Nature of the activity:** probing or reconnaissance only -> MEDIUM; weak or often-benign signal -> LOW.

Severities in section 4 are **initial defaults for the MVP**. They may be revised after the evaluation if results show a rule's severity does not fit. In the MVP severity is fixed per rule. Raising severity automatically when alerts combine is a possible future extension.

## 9. Datasets for evaluation

All datasets are synthetic, generated for this project, with a fixed random seed so they can be regenerated exactly. See the authorised-environment rules in `system-architecture.md` section 3.

| Dataset | Content | Expected detections (rules) |
| --- | --- | --- |
| D1 Normal activity | Typical logins, page views, connections, no attack patterns | None. Used to find false positives |
| D2 Brute-force | Many failed logins from one source | AUTH-001, AUTH-003 (if invalid users included) |
| D3 Suspicious authentication sequence | Repeated failures then success | AUTH-001, AUTH-002 |
| D4 Web scanning-like | Many 404/401/403 responses and indicator-matching requests | WEB-001, WEB-002, WEB-003 |
| D5 Port scanning-like | One source hitting many ports | NET-001, NET-002 |
| D6 Privilege-related | Login followed by privilege change; admin action by non-listed user | PRIV-001, PRIV-002, COR-001 |
| D7 Mixed | All of the above interleaved with normal activity | Union of the above |

Each dataset has a separate **labels file** listing the expected detections: `rule_id`, entity (for example source IP or username) and time range.

## 10. Evaluation methodology

### 10.1 Definitions

| Term | Definition |
| --- | --- |
| Expected detection | An entry in the labels file |
| Actual detection | An alert created by the system |
| **True positive (TP)** | An alert that matches an expected detection: same `rule_id`, same entity, and overlapping time range |
| **False positive (FP)** | An alert with no matching expected detection |
| **False negative (FN)** | An expected detection with no matching alert |
| **Detection rate** | TP / (TP + FN) |
| Precision (extra) | TP / (TP + FP) |

### 10.2 Metrics collected per dataset and per rule

1. Number of events processed
2. Number of expected detections
3. Number of actual detections (alerts)
4. TP, FP and FN counts
5. Detection rate (and precision)
6. **Processing time:** wall-clock time to ingest, normalise and evaluate the whole dataset, and events per second
7. **Alert generation time:** for each alert, the processing time between the engine receiving the event that completes the rule condition and the alert being stored. This measures the platform's own latency and is separate from the event timestamps

### 10.3 Procedure

1. Generate datasets D1-D7 with the documented seed.
2. Start from an empty database and load default rules with the documented parameters.
3. Ingest one dataset, record metrics, then compare alerts with the labels file using the matching rule in 10.1.
4. Repeat each run at least 5 times and report the median and range for timing (detection counts should be identical on every run, and any difference is a bug).
5. Record the environment: operating system, CPU, RAM, Python version, MongoDB version.
6. Change thresholds only between evaluation rounds, and report which version of the parameters produced which results.

### 10.4 Results table (to be filled after testing)

No results exist yet. The table is a template.

| Dataset | Events | Expected | Actual | TP | FP | FN | Detection rate | Processing time | Mean alert generation time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| D2 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| D3 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| D4 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| D5 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| D6 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| D7 | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |

### 10.5 Limits of the evaluation

- The datasets are written by the same team that writes the rules, so high detection rates on them show the rules work as designed, not that they would work on real traffic.
- Results apply only to the parameter values and dataset sizes tested.
- Timing depends on the test machine and is reported only with its specification.
