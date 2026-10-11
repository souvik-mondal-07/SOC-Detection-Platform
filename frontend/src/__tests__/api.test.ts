import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, describeErrorBody, fetchAlerts, fetchRules } from "../services/api";
import { DEFAULT_ALERT_FILTERS } from "../types/alerts";
import { validateAlertFilters } from "../components/alerts/AlertFilters";

const query = { ...DEFAULT_ALERT_FILTERS, page: 2, limit: 50 };

function mockFetch(impl: () => Promise<Response>) {
  const fn = vi.fn((..._args: unknown[]) => impl());
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("describeErrorBody", () => {
  it("reads the {error:{message,details}} shape", () => {
    expect(describeErrorBody({ error: { message: "Validation failed", details: [{ field: "limit", message: "too big" }] } }, 422)).toBe(
      "Validation failed (limit: too big)",
    );
  });
  it("reads the /rules {success:false,message} shape", () => {
    expect(describeErrorBody({ success: false, message: "Rule not found", error_code: "RULE_NOT_FOUND" }, 404)).toBe("Rule not found");
  });
  it("falls back to the status code", () => {
    expect(describeErrorBody("oops", 500)).toBe("Backend responded with status 500");
  });
});

describe("api client", () => {
  it("sends only the filters that are set, with page and limit", async () => {
    const fn = mockFetch(async () => new Response(JSON.stringify({ success: true, page: 2, limit: 50, total: 0, count: 0, alerts: [] })));
    await fetchAlerts({ ...query, severity: "high", priority_min: "40" });
    const url = String(fn.mock.calls[0][0]);
    expect(url).toContain("/alerts?");
    expect(url).toContain("page=2");
    expect(url).toContain("limit=50");
    expect(url).toContain("severity=high");
    expect(url).toContain("priority_min=40");
    expect(url).not.toContain("status=");
    expect(url).not.toContain("source_ip=");
  });

  it("reports an unreachable backend as an error (no fallback data)", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    await expect(fetchAlerts(query)).rejects.toMatchObject({ name: "ApiError", status: 0 });
  });

  it("surfaces HTTP errors with the backend message", async () => {
    mockFetch(async () => new Response(JSON.stringify({ error: { message: "Database is unavailable" } }), { status: 503 }));
    await expect(fetchAlerts({ ...query, page: 3 })).rejects.toThrow("Database is unavailable");
  });

  it("rejects responses with an unexpected shape", async () => {
    mockFetch(async () => new Response(JSON.stringify({ hello: "world" })));
    const error = await fetchRules({ page: 1, limit: 1, category: "", severity: "", enabled: "", name: "" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toMatch(/unexpected format/);
  });

  it("shares identical in-flight requests", async () => {
    const fn = mockFetch(async () => new Response(JSON.stringify({ success: true, page: 1, limit: 1, total: 0, count: 0, alerts: [] })));
    const q = { ...query, page: 1, limit: 1 };
    await Promise.all([fetchAlerts(q), fetchAlerts(q)]);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe("validateAlertFilters", () => {
  it("accepts defaults and valid values", () => {
    expect(validateAlertFilters(DEFAULT_ALERT_FILTERS)).toBeNull();
    expect(validateAlertFilters({ ...DEFAULT_ALERT_FILTERS, priority_min: "10", priority_max: "90", rule_id: "AUTH-001" })).toBeNull();
  });
  it("rejects min > max, out of range and bad rule ids", () => {
    expect(validateAlertFilters({ ...DEFAULT_ALERT_FILTERS, priority_min: "90", priority_max: "10" })).toMatch(/cannot be greater/);
    expect(validateAlertFilters({ ...DEFAULT_ALERT_FILTERS, priority_max: "101" })).toMatch(/0 to 100/);
    expect(validateAlertFilters({ ...DEFAULT_ALERT_FILTERS, rule_id: "bad" })).toMatch(/Rule ID/);
  });
});
