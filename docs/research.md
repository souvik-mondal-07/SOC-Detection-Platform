# Research: Existing Detection Platforms and Project Gap

**Project:** Rule-Based Security Event Detection and Alerting System for Automated Identification of Suspicious Activities
**Research date:** 2 October 2026

## 1. Purpose and method

This document reviews four widely used security monitoring platforms (Wazuh, Splunk, Elastic Security, Microsoft Sentinel) to understand how mature products approach the detection workflow, and to position this project honestly against them.

**Method and limits**

- Only official vendor documentation was used (links in section 6). Third-party blogs and forums were not used as evidence.
- Statements describe what the documentation says each product does. Where a capability was not confirmed in the pages reviewed, the table says "not covered in the pages reviewed". That is not a claim that the capability is absent.
- No weakness or limitation of any product is asserted. Product documentation changes often, so verify against the live pages before citing this document in a final report.
- This project does not aim to compete with these platforms.

## 2. Comparison summary

| Aspect | Wazuh | Splunk (Enterprise Security) | Elastic Security | Microsoft Sentinel |
| --- | --- | --- | --- | --- |
| Purpose | XDR and SIEM platform for cloud, container and server workloads | Security product built on the Splunk platform; correlation searches find defined patterns across data sources | Detection engine and alerting within the Elastic stack | Cloud SIEM that collects, detects, investigates and tracks incidents |
| Log collection | Agents on endpoints, plus agentless monitoring of devices such as firewalls, switches and routers | Platform can index machine data; universal forwarder is the primary way to send data in | Rules run over Elasticsearch indices or data views; Winlogbeat and Elastic Defend data are named in the docs | Data connectors, including Linux/Windows agents, syslog servers and Azure services; data stored in a Log Analytics workspace |
| Detection | Server analyses agent data through decoders and rules | Correlation searches scan multiple data sources for defined patterns | Detection rules evaluated by the detection engine; several rule types | Analytics rules (templates or custom KQL queries) |
| Alerting | Rules generate alerts when all their conditions are met | A match can trigger an adaptive response action; searches can create notable events and risk scores | Alerts created when rule criteria are met; exceptions and alert suppression available | Analytics rules generate alerts, which can be configured to create incidents |
| Dashboards | Web dashboard for visualisation, analysis and configuration | Security Posture dashboard and Incident Review page are named in the docs | Detection & Response dashboard summarises alerts, cases, hosts and users | Overview page lists recent incidents and the general security situation |
| Rule-based detection | XML rules with match conditions and severity level | Searches written in the Splunk search language (SPL), with thresholds | Field-value rules, threshold rules, EQL rules, ML rules and more | Scheduled and near-real-time (NRT) analytics rules |
| Correlation | Composite rules using `frequency`, `timeframe` and `if_matched_sid` | Correlation searches combine data across security domains | EQL rules detect ordered sequences of events | Incidents can group multiple related alerts |
| Target environment | Endpoints, servers, cloud and containers; scales horizontally as a cluster | Organisations running the Splunk platform | Organisations running the Elastic stack | Organisations using Azure and Log Analytics |

## 3. Platform notes

### 3.1 Wazuh

- **Purpose.** The documentation describes Wazuh as providing XDR and SIEM features, including log data analysis, intrusion and malware detection, file integrity monitoring, configuration assessment, vulnerability detection and regulatory compliance support.
- **Architecture.** Agents on endpoints feed three central components: the server (analysis), the indexer (storage and search) and the dashboard (web interface).
- **Rules.** The server processes incoming data through decoders and rules. Rule XML supports match expressions, a `level` attribute, and composite rules built with `frequency` and `timeframe` (seconds) together with `if_matched_sid`, which fires when a referenced rule has matched repeatedly in the window.
- **Relevance to this project.** Wazuh's decoder -> rule -> alert pipeline is the closest published analogue to the planned parse -> normalise -> detect -> alert flow, and its `frequency`/`timeframe` model resembles the threshold rules planned here.

### 3.2 Splunk

- **Purpose.** The Splunk platform can index and monitor IT data including streaming, machine and historical data. Splunk Enterprise Security adds correlation searches for security use cases.
- **Collection.** The universal forwarder is described as the primary way to send data into Splunk.
- **Detection and correlation.** A correlation search scans multiple data sources for defined patterns. Sources can include access, identity, endpoint and network events, asset and identity lists, and threat intelligence. Results are aggregated with SPL functions, and a threshold can be applied, for example to count authentication attempts.
- **Alerting.** A match can run an adaptive response action. Older ES documentation also states that correlation searches can generate notable events and risk scores.
- **Relevance.** Correlation searches that count events against a threshold are the same idea as the project's threshold and sequence rules.

### 3.3 Elastic Security

- **Purpose.** The detection engine evaluates data against detection rules and creates alerts when criteria are met. It also surfaces alerts from Elastic Defend endpoint protection and external tools such as Suricata.
- **Rule types.** The documentation lists several types, from field-value matches to event correlation and machine-learning anomaly detection. EQL (Event Query Language) rules detect ordered sequences of events, and the docs point to threshold rules when a simple count is enough.
- **Operations features.** Prebuilt rules, rule exceptions, alert suppression, and rule monitoring dashboards are documented. The Detection & Response dashboard summarises alerts by status and severity, with related hosts and users.
- **Relevance.** Elastic's own guidance separates simple threshold detection from ordered-sequence correlation. This project makes the same distinction between `threshold` and `sequence` rule types.

### 3.4 Microsoft Sentinel

- **Purpose.** Sentinel helps teams organise, investigate and track incidents from creation to resolution.
- **Collection.** Data connectors ingest from Linux and Windows machines running an agent, from syslog servers for devices such as firewalls and proxies, and directly from Azure services. Events are stored in a Log Analytics workspace.
- **Detection.** Analytics rules are created from built-in templates or custom KQL queries. Rule kinds include scheduled rules, which run at regular intervals over a lookback period, and NRT rules. Hunting queries let analysts look for anomalies that scheduled rules do not cover.
- **Alerting and correlation.** Rules generate alerts, which can create incidents. Incidents can contain multiple related alerts, and the documentation describes analytics that combine lower-fidelity alerts into potential higher-fidelity incidents.
- **Relevance.** The alert -> incident -> investigation -> resolution flow informs this project's alert lifecycle.

## 4. Project gap

> Enterprise security monitoring platforms provide extensive functionality, but their breadth and complexity can make it difficult for learners and small controlled environments to understand the complete detection workflow from raw events to detection rules, alerts, investigation, and evaluation.

This is a statement about learning and small-scale use, not about product quality. The platforms above are built for large, varied environments, and that breadth is appropriate for their purpose.

**How this project addresses the gap**

- **Transparency.** A small codebase where every step is visible: parse, normalise, evaluate rule, create alert, investigate.
- **Readable rules.** Rules are plain data (JSON) with a documented schema, so a learner can read a rule and predict what it will match.
- **Complete loop in one place.** Ingestion, detection, alerting, investigation and a dashboard in a single small project.
- **Measurable.** Controlled synthetic datasets with known expected detections make it possible to measure detection rate, false positives and timing (see `architecture/detection-strategy.md`).
- **Safe by construction.** Synthetic data only, no real targets, no offensive tooling.

**What it deliberately does not do:** replace a SIEM, scale across large fleets, ingest unauthorised data, or automate response.

## 5. Lessons carried into the design

| Observation from the research | Design decision |
| --- | --- |
| Wazuh and Splunk express count-in-window detections declaratively | Threshold rules are data (`threshold`, `window_minutes`), not code |
| Elastic distinguishes threshold rules from ordered-sequence (EQL) rules | Separate `threshold` and `sequence` rule types |
| Sentinel and Elastic both attach severity to rules and track alerts through investigation | Rules carry a default severity; alerts have a status lifecycle |
| Elastic documents testing rules and monitoring rule health | Evaluation methodology with labelled datasets |
| Sentinel and Elastic both document tuning mechanisms (exceptions, suppression) | Planned alert de-duplication window per rule and group key |

## 6. References (official documentation)

**Wazuh**
- Components and overview: https://documentation.wazuh.com/current/user-manual/overview.html
- Rules syntax: https://documentation.wazuh.com/current/user-manual/ruleset/ruleset-xml-syntax/rules.html

**Splunk**
- Correlation search overview (Enterprise Security): https://docs.splunk.com/Documentation/ES/latest/User/CorrelationOverview
- Create correlation searches (older ES release, source for notable events and risk scores): https://docs.splunk.com/Documentation/ES/4.1.1/User/CreateCorrelationSearches
- Universal forwarder: https://www.splunk.com/en_us/blog/learn/splunk-universal-forwarder

**Elastic Security**
- Detections and alerts overview: https://www.elastic.co/guide/en/security/current/detection-engine-overview.html
- Event correlation (EQL) rules: https://www.elastic.co/docs/solutions/security/detect-and-alert/eql
- Detection & Response dashboard: https://elastic.co/guide/en/serverless/current/security-detection-response-dashboard.html

**Microsoft Sentinel**
- Understand incidents: https://learn.microsoft.com/en-us/training/modules/incident-management-sentinel/3-describe-incident-management
- Solution quality guidance (analytics rules, hunting queries): https://learn.microsoft.com/en-us/azure/sentinel/sentinel-solution-quality-guidance
- Analytics rules, scheduled and NRT kinds: https://learn.microsoft.com/en-us/azure/sentinel/isv/sentinel-analytic-rules-creation
