import type { AlertDetail, AlertListResponse, AlertQuery, AlertStats } from "../types/alerts";
import type { EventFilters, EventListResponse, SecurityEvent } from "../types/events";
import type { HealthResponse } from "../types/health";
import type { InvestigationDetail, InvestigationListResponse, InvestigationQuery } from "../types/investigations";
import type { RuleDetail, RuleListResponse, RuleQuery } from "../types/rules";
import { isAlertList, isAlertResponse, isAlertStats, isEventList, isHealth, isInvestigationList, isInvestigationResponse, isRecord, isRuleList, isRuleResponse, isSecurityEvent } from "./guards";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Error with a message that is safe to show. status 0 means the backend could not be reached at all. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** The configured API address without any credentials, query or fragment, safe to display. */
export function getApiBaseUrlForDisplay(): string {
  try {
    const url = new URL(API_BASE_URL);
    return `${url.origin}${url.pathname.replace(/\/$/, "")}`;
  } catch {
    return "(invalid VITE_API_BASE_URL)";
  }
}

function describeDetails(details: unknown): string[] {
  if (!Array.isArray(details)) return [];
  return details
    .map((item) => {
      if (!isRecord(item) || typeof item.message !== "string") return null;
      return `${typeof item.field === "string" ? `${item.field}: ` : ""}${item.message}`;
    })
    .filter((text): text is string => text !== null);
}

/**
 * The backend uses two error shapes: {"error": {"message", "details"}} for most routes and
 * {"success": false, "message", "error_code", "details"} for /rules. FastAPI's own {"detail"} is handled too.
 */
export function describeErrorBody(body: unknown, status: number): string {
  if (isRecord(body)) {
    const nested = isRecord(body.error) ? body.error : null;
    const message = typeof nested?.message === "string" ? nested.message : typeof body.message === "string" ? body.message : null;
    const details = describeDetails(nested?.details ?? body.details);
    if (message) return details.length > 0 ? `${message} (${details.join("; ")})` : message;
    if (typeof body.detail === "string") return body.detail;
  }
  return `Backend responded with status ${status}`;
}

async function describeFailure(response: Response): Promise<string> {
  try {
    return describeErrorBody(await response.json(), response.status);
  } catch {
    return `Backend responded with status ${response.status}`;
  }
}

/** True for the error thrown when a request is cancelled. Cancellation is expected and is never shown as an API failure. */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException ? error.name === "AbortError" : error instanceof Error && error.name === "AbortError";
}

async function request<T>(path: string, guard: (body: unknown) => body is T, signal: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { signal });
  } catch (error) {
    if (isAbortError(error) || signal.aborted) throw abortError();
    throw new ApiError("Cannot reach the backend. Check that it is running and that VITE_API_BASE_URL is correct.", 0);
  }
  if (!response.ok) throw new ApiError(await describeFailure(response), response.status);
  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    if (isAbortError(error) || signal.aborted) throw abortError();
    throw new ApiError("The backend returned a response that is not valid JSON.", response.status);
  }
  if (!guard(body)) throw new ApiError("The backend returned data in an unexpected format.", response.status);
  return body;
}

function abortError(): DOMException {
  return new DOMException("Request aborted", "AbortError");
}

// Identical GET requests that are already running share one network call. The call is reference counted: it is only
// cancelled when every consumer has aborted, so one component unmounting or changing filters never cancels a request
// that another active component still needs.
interface SharedRequest {
  promise: Promise<unknown>;
  controller: AbortController;
  consumers: number;
}
const inFlight = new Map<string, SharedRequest>();

function getJson<T>(path: string, guard: (body: unknown) => body is T, signal?: AbortSignal): Promise<T> {
  if (signal?.aborted) return Promise.reject(abortError());

  let shared = inFlight.get(path);
  if (!shared) {
    const controller = new AbortController();
    const created: SharedRequest = { controller, consumers: 0, promise: Promise.resolve() };
    created.promise = request(path, guard, controller.signal).finally(() => {
      if (inFlight.get(path) === created) inFlight.delete(path);
    });
    created.promise.catch(() => undefined); // each consumer handles its own rejection
    inFlight.set(path, created);
    shared = created;
  }

  const entry = shared;
  entry.consumers += 1;
  return new Promise<T>((resolve, reject) => {
    let done = false;
    const release = () => {
      done = true;
      signal?.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      if (done) return;
      release();
      entry.consumers -= 1;
      if (entry.consumers === 0) {
        if (inFlight.get(path) === entry) inFlight.delete(path);
        entry.controller.abort();
      }
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
    (entry.promise as Promise<T>).then(
      (value) => {
        if (done) return;
        release();
        entry.consumers -= 1;
        resolve(value);
      },
      (error: unknown) => {
        if (done) return;
        release();
        entry.consumers -= 1;
        reject(error);
      },
    );
  });
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    const text = String(value).trim();
    if (text !== "") search.set(key, text);
  }
  return search.toString();
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson("/health", isHealth, signal);
}

/** GET /events: newest first, only the filters the backend supports (no page or offset). */
export function fetchEvents(filters: EventFilters, signal?: AbortSignal): Promise<EventListResponse> {
  const { source, event_type, status, source_ip, limit } = filters;
  return getJson(`/events?${toQuery({ limit, source, event_type, status, source_ip })}`, isEventList, signal);
}

/** GET /events/{event_id} */
export function fetchEvent(eventId: string, signal?: AbortSignal): Promise<SecurityEvent> {
  return getJson(`/events/${encodeURIComponent(eventId)}`, isSecurityEvent, signal);
}

/** GET /alerts: the backend sorts by priority_score desc, then newest first. */
export function fetchAlerts(query: AlertQuery, signal?: AbortSignal): Promise<AlertListResponse> {
  const { page, limit, severity, status, rule_id, source_ip, priority_min, priority_max } = query;
  return getJson(`/alerts?${toQuery({ page, limit, severity, status, rule_id, source_ip, priority_min, priority_max })}`, isAlertList, signal);
}

/** GET /alerts/{alert_id}: the list items omit description, event_ids and updated_at. */
export async function fetchAlert(alertId: string, signal?: AbortSignal): Promise<AlertDetail> {
  return (await getJson(`/alerts/${encodeURIComponent(alertId)}`, isAlertResponse, signal)).alert;
}

/** GET /alerts/stats: exact lifecycle, severity and active counts across all alerts. */
export function fetchAlertStats(signal?: AbortSignal): Promise<AlertStats> {
  return getJson("/alerts/stats", isAlertStats, signal);
}

/** GET /investigations?alert_id=...: investigations that reference this alert (investigation status is not alert status). */
export function fetchInvestigationsForAlert(alertId: string, signal?: AbortSignal): Promise<InvestigationListResponse> {
  return getJson(`/investigations?${toQuery({ alert_id: alertId, limit: 20 })}`, isInvestigationList, signal);
}

/** GET /rules */
export function fetchRules(query: RuleQuery, signal?: AbortSignal): Promise<RuleListResponse> {
  const { page, limit, category, severity, enabled, name } = query;
  return getJson(`/rules?${toQuery({ page, limit, category, severity, enabled, name })}`, isRuleList, signal);
}

/** GET /rules/{rule_id} */
export async function fetchRule(ruleId: string, signal?: AbortSignal): Promise<RuleDetail> {
  return (await getJson(`/rules/${encodeURIComponent(ruleId)}`, isRuleResponse, signal)).rule;
}

// -- Investigations (Step 11). Writes are never shared or de-duplicated like GETs, and the body is always JSON. --

async function sendJson<T>(method: "POST" | "PATCH" | "DELETE", path: string, body: unknown, guard: (body: unknown) => body is T): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the backend. Check that it is running and that VITE_API_BASE_URL is correct.", 0);
  }
  if (!response.ok) throw new ApiError(await describeFailure(response), response.status);
  let json: unknown;
  try {
    json = await response.json();
  } catch {
    throw new ApiError("The backend returned a response that is not valid JSON.", response.status);
  }
  if (!guard(json)) throw new ApiError("The backend returned data in an unexpected format.", response.status);
  return json;
}

const investigationPath = (id: string) => `/investigations/${encodeURIComponent(id)}`;

/** GET /investigations: newest first. */
export function fetchInvestigations(query: InvestigationQuery, signal?: AbortSignal): Promise<InvestigationListResponse> {
  const { page, limit, status, title } = query;
  return getJson(`/investigations?${toQuery({ page, limit, status, title })}`, isInvestigationList, signal);
}

/** GET /investigations/{id}: includes live context for every linked alert and all notes. */
export async function fetchInvestigation(id: string, signal?: AbortSignal): Promise<InvestigationDetail> {
  return (await getJson(investigationPath(id), isInvestigationResponse, signal)).investigation;
}

/** POST /investigations */
export async function createInvestigation(title: string, alertIds: readonly string[]): Promise<InvestigationDetail> {
  return (await sendJson("POST", "/investigations", { title: title.trim(), alert_ids: alertIds }, isInvestigationResponse)).investigation;
}

/** PATCH /investigations/{id}: title and/or investigation status only. */
export async function updateInvestigation(id: string, changes: { title?: string; status?: string }): Promise<InvestigationDetail> {
  return (await sendJson("PATCH", investigationPath(id), changes, isInvestigationResponse)).investigation;
}

/** POST /investigations/{id}/alerts */
export async function linkAlerts(id: string, alertIds: readonly string[]): Promise<InvestigationDetail> {
  return (await sendJson("POST", `${investigationPath(id)}/alerts`, { alert_ids: alertIds }, isInvestigationResponse)).investigation;
}

/** DELETE /investigations/{id}/alerts/{alert_id}: removes the link only. */
export async function unlinkAlert(id: string, alertId: string): Promise<InvestigationDetail> {
  return (await sendJson("DELETE", `${investigationPath(id)}/alerts/${encodeURIComponent(alertId)}`, undefined, isInvestigationResponse)).investigation;
}

/** POST /investigations/{id}/notes */
export async function addInvestigationNote(id: string, text: string): Promise<InvestigationDetail> {
  return (await sendJson("POST", `${investigationPath(id)}/notes`, { text: text.trim() }, isInvestigationResponse)).investigation;
}

// -- Alert lifecycle (Step 12). Resolves only after the backend has confirmed the change; callers must not show success earlier. --

/** PATCH /alerts/{id}/status. `reason` is the resolution note, false-positive reason or reopen reason. */
export async function changeAlertStatus(alertId: string, status: string, reason?: string): Promise<AlertDetail> {
  const trimmed = reason?.trim();
  const body = trimmed ? { status, reason: trimmed } : { status };
  return (await sendJson("PATCH", `/alerts/${encodeURIComponent(alertId)}/status`, body, isAlertResponse)).alert;
}

/** POST /alerts/{id}/acknowledge: status stays open. */
export async function acknowledgeAlert(alertId: string): Promise<AlertDetail> {
  return (await sendJson("POST", `/alerts/${encodeURIComponent(alertId)}/acknowledge`, undefined, isAlertResponse)).alert;
}
