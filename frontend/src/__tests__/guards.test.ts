import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchAlert, fetchAlerts, fetchEvents, fetchHealth, fetchRule, fetchRules } from "../services/api";
import { DEFAULT_ALERT_FILTERS } from "../types/alerts";

const alertItem = { alert_id: "ALT-1", rule_id: "AUTH-001", title: "t", severity: "high", priority_score: 80, priority_reason: null, status: "open", source_ip: null, created_at: "2026-10-09T00:00:00Z" };
const event = { event_id: "evt_1", timestamp: "2026-10-09T00:00:00Z", source: "linux_auth", event_type: "authentication", action: "login", status: "failed", username: null, source_ip: "10.0.0.1", message: "m", metadata: {}, created_at: "2026-10-09T00:00:00Z" };
const rule = { rule_id: "AUTH-001", name: "n", category: "authentication", severity: "high", enabled: true };
const alertQuery = { ...DEFAULT_ALERT_FILTERS, page: 1, limit: 20 };
const ruleQuery = { page: 1, limit: 20, category: "", severity: "", enabled: "" as const, name: "" };

function respond(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body))));
}
const listOf = (alerts: unknown[]) => ({ success: true, page: 1, limit: 20, total: alerts.length, count: alerts.length, alerts });

afterEach(() => vi.unstubAllGlobals());

describe("response guards", () => {
  it("accepts valid alert, event, rule and health responses, including missing optional fields", async () => {
    respond(listOf([alertItem, { ...alertItem, alert_id: "ALT-2", priority_reason: undefined, source_ip: undefined }]));
    expect((await fetchAlerts(alertQuery)).alerts).toHaveLength(2);
    respond({ count: 1, events: [event, { ...event, event_id: "evt_2", username: undefined }] });
    expect((await fetchEvents({ source: "", event_type: "", status: "", source_ip: "", limit: 50 })).events).toHaveLength(2);
    respond({ success: true, ...ruleQuery, total: 1, count: 1, rules: [rule] });
    expect((await fetchRules(ruleQuery)).rules).toHaveLength(1);
    respond({ status: "ok", message: "x", service: "s", version: "1", environment: "dev", database: "connected", timestamp: "t" });
    expect((await fetchHealth()).database).toBe("connected");
  });

  it.each([
    ["alert without priority_score", () => fetchAlerts(alertQuery), listOf([{ ...alertItem, priority_score: undefined }])],
    ["alert with a non-string title", () => fetchAlerts(alertQuery), listOf([{ ...alertItem, title: 5 }])],
    ["alert list with a null item", () => fetchAlerts(alertQuery), listOf([null])],
    ["alert list with a negative total", () => fetchAlerts(alertQuery), { ...listOf([]), total: -1 }],
    ["alert detail without event_ids", () => fetchAlert("ALT-1"), { success: true, alert: { ...alertItem, description: "d", updated_at: "t" } }],
    ["alert detail with non-string event_ids", () => fetchAlert("ALT-1"), { success: true, alert: { ...alertItem, description: "d", updated_at: "t", event_ids: [1] } }],
    ["event without metadata", () => fetchEvents({ source: "", event_type: "", status: "", source_ip: "", limit: 1 }), { count: 1, events: [{ ...event, metadata: undefined }] }],
    ["event with a numeric message", () => fetchEvents({ source: "", event_type: "", status: "", source_ip: "", limit: 1 }), { count: 1, events: [{ ...event, message: 7 }] }],
    ["rule with a string enabled flag", () => fetchRules(ruleQuery), { success: true, page: 1, limit: 20, total: 1, count: 1, rules: [{ ...rule, enabled: "yes" }] }],
    ["rule detail without conditions", () => fetchRule("AUTH-001"), { success: true, rule: { ...rule, description: "d", created_at: "t", updated_at: "t" } }],
    ["health with an unknown database state", () => fetchHealth(), { status: "ok", service: "s", version: "1", environment: "e", database: "maybe" }],
  ])("rejects %s with a readable error", async (_name, call, body) => {
    respond(body);
    const error = await call().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toMatch(/unexpected format/);
  });
});
