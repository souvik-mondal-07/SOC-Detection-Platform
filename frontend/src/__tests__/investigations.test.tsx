// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import NotesPanel from "../components/investigations/NotesPanel";
import StatusControl from "../components/investigations/StatusControl";
import {
  addInvestigationNote, createInvestigation, fetchInvestigations, linkAlerts, unlinkAlert, updateInvestigation,
} from "../services/api";
import { isInvestigationList, isInvestigationResponse } from "../services/guards";
import { DEFAULT_INVESTIGATION_FILTERS, INVESTIGATION_STATUSES, STATUS_TRANSITIONS, validateNote, validateTitle } from "../types/investigations";

const detail = {
  investigation_id: "INV-20261014-000001", title: "t", status: "open", alert_count: 1, note_count: 1,
  created_at: "2026-10-14T10:00:00Z", updated_at: "2026-10-14T10:00:00Z", alert_ids: ["ALT-1"], unavailable_alert_count: 1,
  alerts: [
    { alert_id: "ALT-1", available: true, rule_id: "AUTH-001", title: "x", severity: "high", priority_score: 80, status: "open", source_ip: null, created_at: "2026-10-14T10:00:00Z", event_count: 1, event_ids: ["evt_1"] },
    { alert_id: "ALT-2", available: false, rule_id: null, title: null, severity: null, priority_score: null, status: null, source_ip: null, created_at: null, event_count: 0, event_ids: [] },
  ],
  notes: [{ note_id: "note_1", text: "hello", created_at: "2026-10-14T10:05:00Z" }],
};

function mockFetch(body: unknown, status = 200) {
  const fn = vi.fn((..._args: unknown[]) => Promise.resolve(new Response(JSON.stringify(body), { status })));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("investigation guards", () => {
  it("accepts a valid detail, including an unavailable alert", () => {
    expect(isInvestigationResponse({ success: true, investigation: detail })).toBe(true);
  });
  it("rejects malformed responses", () => {
    expect(isInvestigationResponse({ investigation: { ...detail, notes: [{ text: "no id" }] } })).toBe(false);
    expect(isInvestigationResponse({ investigation: { ...detail, alerts: [{ alert_id: 1 }] } })).toBe(false);
    expect(isInvestigationList({ page: 1, limit: 1, total: 0, count: 0, investigations: [{ nope: true }] })).toBe(false);
    expect(isInvestigationList({ page: 1, limit: 20, total: 0, count: 0, investigations: [] })).toBe(true);
  });
});

describe("investigation api client", () => {
  it("sends list filters and omits empty ones", async () => {
    const fn = mockFetch({ success: true, page: 2, limit: 10, total: 0, count: 0, investigations: [] });
    await fetchInvestigations({ ...DEFAULT_INVESTIGATION_FILTERS, status: "closed", page: 2, limit: 10 });
    const url = String(fn.mock.calls[0][0]);
    expect(url).toContain("/investigations?");
    expect(url).toContain("status=closed");
    expect(url).toContain("page=2");
    expect(url).not.toContain("title=");
  });

  it("creates, patches, links, unlinks and adds notes with the right method, path and body", async () => {
    const fn = mockFetch({ success: true, investigation: detail });
    await createInvestigation("  My title ", ["ALT-1"]);
    await updateInvestigation("INV-1", { status: "closed" });
    await linkAlerts("INV-1", ["ALT-2"]);
    await unlinkAlert("INV-1", "ALT-2");
    await addInvestigationNote("INV-1", "  finding ");
    const calls = fn.mock.calls.map(([url, init]) => [String(url).replace(/^.*\/api\/v1/, ""), (init as RequestInit).method, (init as RequestInit).body]);
    expect(calls).toEqual([
      ["/investigations", "POST", JSON.stringify({ title: "My title", alert_ids: ["ALT-1"] })],
      ["/investigations/INV-1", "PATCH", JSON.stringify({ status: "closed" })],
      ["/investigations/INV-1/alerts", "POST", JSON.stringify({ alert_ids: ["ALT-2"] })],
      ["/investigations/INV-1/alerts/ALT-2", "DELETE", undefined],
      ["/investigations/INV-1/notes", "POST", JSON.stringify({ text: "finding" })],
    ]);
  });

  it("surfaces backend errors and unreachable backend as ApiError", async () => {
    mockFetch({ error: { message: "Alert already linked: ALT-1" } }, 409);
    await expect(linkAlerts("INV-1", ["ALT-1"])).rejects.toThrow("Alert already linked: ALT-1");
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(addInvestigationNote("INV-1", "x")).rejects.toMatchObject({ name: "ApiError", status: 0 });
  });

  it("rejects an unexpected response shape", async () => {
    mockFetch({ hello: "world" });
    await expect(updateInvestigation("INV-1", { title: "x" })).rejects.toThrow(/unexpected format/);
  });
});

describe("validation and transitions", () => {
  it("validates titles and notes like the backend", () => {
    expect(validateTitle("  ")).toMatch(/title/i);
    expect(validateTitle("x".repeat(201))).toMatch(/200/);
    expect(validateTitle("ok")).toBeNull();
    expect(validateNote("   ")).toMatch(/note/i);
    expect(validateNote("x".repeat(2001))).toMatch(/2000/);
    expect(validateNote("x".repeat(2000))).toBeNull();
  });
  it("matches the backend transition table", () => {
    expect(INVESTIGATION_STATUSES).toEqual(["open", "in_progress", "closed"]);
    expect(STATUS_TRANSITIONS.closed).toEqual(["in_progress"]);
    expect(STATUS_TRANSITIONS.open).not.toContain("open");
  });
});

describe("StatusControl", () => {
  it("offers only allowed next statuses and reports the choice", () => {
    const onChange = vi.fn();
    render(<StatusControl status="closed" busy={false} onChange={onChange} />);
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["Select status…", "In progress"]);
    expect((screen.getByRole("button", { name: "Update status" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Change to"), { target: { value: "in_progress" } });
    fireEvent.click(screen.getByRole("button", { name: "Update status" }));
    expect(onChange).toHaveBeenCalledWith("in_progress");
  });
});

describe("NotesPanel", () => {
  it("shows notes oldest first as plain text", () => {
    render(<NotesPanel investigationId="INV-1" notes={[{ note_id: "a", text: "<b>first</b>", created_at: "2026-10-14T10:00:00Z" }, { note_id: "b", text: "second", created_at: "2026-10-14T11:00:00Z" }]} onAdded={vi.fn()} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0].textContent).toContain("<b>first</b>");
    expect(items[1].textContent).toContain("second");
    expect(document.querySelector("b")).toBeNull();
  });

  it("blocks empty notes without calling the backend", () => {
    const fn = mockFetch({});
    render(<NotesPanel investigationId="INV-1" notes={[]} onAdded={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Add a note"), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(screen.getByRole("alert").textContent).toMatch(/Write a note/);
    expect(fn).not.toHaveBeenCalled();
  });

  it("submits a note, clears the form and reports success; shows backend errors", async () => {
    const onAdded = vi.fn();
    mockFetch({ success: true, investigation: detail }, 201);
    render(<NotesPanel investigationId="INV-1" notes={[]} onAdded={onAdded} />);
    fireEvent.change(screen.getByLabelText("Add a note"), { target: { value: "finding" } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalledTimes(1));
    expect((screen.getByLabelText("Add a note") as HTMLTextAreaElement).value).toBe("");
    expect(screen.getByRole("status", { name: "" }).textContent).toMatch(/Note added/);

    mockFetch({ error: { message: "Investigation not found" } }, 404);
    fireEvent.change(screen.getByLabelText("Add a note"), { target: { value: "again" } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Investigation not found"));
    expect((screen.getByLabelText("Add a note") as HTMLTextAreaElement).value).toBe("again"); // draft kept
  });
});
