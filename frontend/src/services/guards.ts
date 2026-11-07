// Runtime checks for backend responses. They verify every field the tables, detail views and charts read, so a response in
// an unexpected format becomes a readable ApiError instead of a crash while rendering. Optional fields may be missing or null.
import type { AlertDetail, AlertListItem, AlertListResponse, AlertResponse } from "../types/alerts";
import type { SecurityEvent, EventListResponse } from "../types/events";
import type { HealthResponse } from "../types/health";
import type { InvestigationDetail, InvestigationListItem, InvestigationListResponse, InvestigationNote, InvestigationResponse, LinkedAlert } from "../types/investigations";
import type { RuleDetail, RuleListResponse, RuleResponse, RuleSummary } from "../types/rules";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const isString = (v: unknown): v is string => typeof v === "string";
const isCount = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v) && v >= 0;
const isScore = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isOptionalString = (v: unknown): boolean => v === undefined || v === null || typeof v === "string";
const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every(isString);
const allStrings = (r: Record<string, unknown>, keys: readonly string[]): boolean => keys.every((k) => isString(r[k]));
const allOptionalStrings = (r: Record<string, unknown>, keys: readonly string[]): boolean => keys.every((k) => isOptionalString(r[k]));

export function isHealth(b: unknown): b is HealthResponse {
  return isRecord(b) && allStrings(b, ["status", "service", "version", "environment"]) && (b.database === "connected" || b.database === "unavailable");
}

export function isSecurityEvent(b: unknown): b is SecurityEvent {
  return (
    isRecord(b) &&
    allStrings(b, ["event_id", "timestamp", "source", "event_type", "action", "status", "message", "created_at"]) &&
    allOptionalStrings(b, ["username", "source_ip"]) &&
    isRecord(b.metadata)
  );
}

export function isEventList(b: unknown): b is EventListResponse {
  return isRecord(b) && isCount(b.count) && Array.isArray(b.events) && b.events.every(isSecurityEvent);
}

export function isAlertListItem(b: unknown): b is AlertListItem {
  return (
    isRecord(b) &&
    allStrings(b, ["alert_id", "rule_id", "title", "severity", "status", "created_at"]) &&
    isScore(b.priority_score) &&
    allOptionalStrings(b, ["priority_reason", "source_ip"])
  );
}

export function isAlertDetail(b: unknown): b is AlertDetail {
  return isAlertListItem(b) && allStrings(b as unknown as Record<string, unknown>, ["description", "updated_at"]) && isStringArray((b as unknown as Record<string, unknown>).event_ids);
}

export function isAlertList(b: unknown): b is AlertListResponse {
  return (
    isRecord(b) && isCount(b.page) && isCount(b.limit) && isCount(b.total) && isCount(b.count) && Array.isArray(b.alerts) && b.alerts.every(isAlertListItem)
  );
}

export function isAlertResponse(b: unknown): b is AlertResponse {
  return isRecord(b) && isAlertDetail(b.alert);
}

export function isRuleSummary(b: unknown): b is RuleSummary {
  return isRecord(b) && allStrings(b, ["rule_id", "name", "category", "severity"]) && typeof b.enabled === "boolean";
}

export function isRuleDetail(b: unknown): b is RuleDetail {
  return isRuleSummary(b) && allStrings(b as unknown as Record<string, unknown>, ["description", "created_at", "updated_at"]) && isRecord((b as unknown as Record<string, unknown>).conditions);
}

export function isRuleList(b: unknown): b is RuleListResponse {
  return isRecord(b) && isCount(b.page) && isCount(b.limit) && isCount(b.total) && isCount(b.count) && Array.isArray(b.rules) && b.rules.every(isRuleSummary);
}

export function isRuleResponse(b: unknown): b is RuleResponse {
  return isRecord(b) && isRuleDetail(b.rule);
}

const isOptionalScore = (v: unknown): boolean => v === undefined || v === null || isScore(v);

export function isInvestigationListItem(b: unknown): b is InvestigationListItem {
  return isRecord(b) && allStrings(b, ["investigation_id", "title", "status", "created_at", "updated_at"]) && isCount(b.alert_count) && isCount(b.note_count);
}

export function isInvestigationNote(b: unknown): b is InvestigationNote {
  return isRecord(b) && allStrings(b, ["note_id", "text", "created_at"]);
}

export function isLinkedAlert(b: unknown): b is LinkedAlert {
  return (
    isRecord(b) &&
    isString(b.alert_id) &&
    typeof b.available === "boolean" &&
    allOptionalStrings(b, ["rule_id", "title", "severity", "status", "source_ip", "created_at"]) &&
    isOptionalScore(b.priority_score) &&
    isCount(b.event_count) &&
    isStringArray(b.event_ids)
  );
}

export function isInvestigationDetail(b: unknown): b is InvestigationDetail {
  if (!isInvestigationListItem(b)) return false;
  const r = b as unknown as Record<string, unknown>;
  return isStringArray(r.alert_ids) && Array.isArray(r.alerts) && r.alerts.every(isLinkedAlert) && Array.isArray(r.notes) && r.notes.every(isInvestigationNote) && isCount(r.unavailable_alert_count);
}

export function isInvestigationList(b: unknown): b is InvestigationListResponse {
  return isRecord(b) && isCount(b.page) && isCount(b.limit) && isCount(b.total) && isCount(b.count) && Array.isArray(b.investigations) && b.investigations.every(isInvestigationListItem);
}

export function isInvestigationResponse(b: unknown): b is InvestigationResponse {
  return isRecord(b) && isInvestigationDetail(b.investigation);
}
