// Runtime checks for backend responses. They verify every field the tables, detail views and charts read, so a response in
// an unexpected format becomes a readable ApiError instead of a crash while rendering. Optional fields may be missing or null.
import type { AlertDetail, AlertListItem, AlertListResponse, AlertResponse } from "../types/alerts";
import type { SecurityEvent, EventListResponse } from "../types/events";
import type { HealthResponse } from "../types/health";
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
