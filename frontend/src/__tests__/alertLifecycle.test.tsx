// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import AlertDetails from "../components/alerts/AlertDetails";
import AlertLifecyclePanel from "../components/alerts/AlertLifecyclePanel";
import AlertTable from "../components/alerts/AlertTable";
import StatusTimeline from "../components/alerts/StatusTimeline";
import { acknowledgeAlert, changeAlertStatus, fetchAlertStats } from "../services/api";
import { isAlertDetail, isAlertStats } from "../services/guards";
import { ALERT_STATUSES, ALERT_TRANSITIONS, availableActions, canAcknowledge, validateReason, type AlertDetail } from "../types/alerts";

const base: AlertDetail = {
  alert_id: "ALT-1", rule_id: "AUTH-001", title: "Multiple Failed Logins Detected", severity: "high", priority_score: 83, priority_reason: null,
  status: "open", source_ip: "10.0.0.1", created_at: "2026-11-05T10:00:00Z", updated_at: "2026-11-05T10:00:00Z", acknowledged_at: null,
  description: "d", event_ids: ["evt_1"], resolution_note: null, status_history: [],
};
const withStatus = (status: string, extra: Partial<AlertDetail> = {}): AlertDetail => ({ ...base, status, ...extra });

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("guards and rules", () => {
  it("requires status_history on alert details and validates its entries", () => {
    expect(isAlertDetail(base)).toBe(true);
    const { status_history: _omit, ...without } = base;
    expect(isAlertDetail(without)).toBe(false);
    expect(isAlertDetail({ ...base, status_history: [{ nope: 1 }] })).toBe(false);
    expect(isAlertDetail({ ...base, status_history: [{ action: "status_change", previous_status: "open", new_status: "resolved", timestamp: "t", reason: null }] })).toBe(true);
  });

  it("validates the stats response", () => {
    const stats = { success: true, total: 3, by_status: { open: 3 }, by_severity: { high: 3 }, active: 3, high_critical_active: 3, acknowledged_open: 0 };
    expect(isAlertStats(stats)).toBe(true);
    expect(isAlertStats({ ...stats, total: "3" })).toBe(false);
    expect(isAlertStats({ ...stats, by_status: { open: -1 } })).toBe(false);
  });

  it("mirrors the backend transition table", () => {
    expect(ALERT_TRANSITIONS).toEqual({
      open: ["investigating", "resolved", "false_positive"],
      investigating: ["open", "resolved", "false_positive"],
      resolved: ["open"],
      false_positive: ["open"],
    });
    for (const status of ALERT_STATUSES) expect(ALERT_TRANSITIONS[status]).not.toContain(status);
  });

  it("offers only valid actions and none for unknown statuses", () => {
    expect(availableActions("open").map((a) => a.label)).toEqual(["Start investigating", "Resolve", "Mark false positive"]);
    expect(availableActions("resolved").map((a) => a.label)).toEqual(["Reopen"]);
    expect(availableActions("false_positive").map((a) => [a.label, a.needsReason])).toEqual([["Reopen", true]]);
    expect(availableActions("investigating").find((a) => a.to === "open")?.needsReason).toBe(false);
    expect(availableActions("bogus")).toEqual([]);
    expect(availableActions("__proto__")).toEqual([]);
  });

  it("only open, unacknowledged alerts can be acknowledged", () => {
    expect(canAcknowledge({ status: "open" })).toBe(true);
    expect(canAcknowledge({ status: "open", acknowledged_at: "2026-11-05T10:00:00Z" })).toBe(false);
    expect(canAcknowledge({ status: "investigating" })).toBe(false);
  });

  it("validates reasons", () => {
    expect(validateReason("   ", true)).toMatch(/required/);
    expect(validateReason("", false)).toBeNull();
    expect(validateReason("x".repeat(1001), false)).toMatch(/1000/);
    expect(validateReason("x".repeat(1000), true)).toBeNull();
  });
});

describe("api client", () => {
  it("sends status changes with the right method, path and trimmed body", async () => {
    const fn = vi.fn((..._a: unknown[]) => Promise.resolve(json({ success: true, alert: base })));
    vi.stubGlobal("fetch", fn);
    await changeAlertStatus("ALT-1", "resolved", "  done  ");
    await changeAlertStatus("ALT-1", "investigating", "   ");
    await acknowledgeAlert("ALT-1");
    const calls = fn.mock.calls.map(([url, init]) => [String(url).replace(/^.*\/api\/v1/, ""), (init as RequestInit).method, (init as RequestInit).body]);
    expect(calls).toEqual([
      ["/alerts/ALT-1/status", "PATCH", JSON.stringify({ status: "resolved", reason: "done" })],
      ["/alerts/ALT-1/status", "PATCH", JSON.stringify({ status: "investigating" })],
      ["/alerts/ALT-1/acknowledge", "POST", undefined],
    ]);
  });

  it("surfaces backend errors and bad response shapes", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(json({ error: { message: "The alert is already resolved" } }, 409))));
    await expect(changeAlertStatus("ALT-1", "resolved", "x")).rejects.toThrow("The alert is already resolved");
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(json({ success: true, alert: { alert_id: "x" } }))));
    await expect(acknowledgeAlert("ALT-1")).rejects.toThrow(/unexpected format/);
  });

  it("reads exact counts from /alerts/stats", async () => {
    const stats = { success: true, total: 2, by_status: { open: 1, resolved: 1 }, by_severity: { high: 2 }, active: 1, high_critical_active: 1, acknowledged_open: 0 };
    const fn = vi.fn((..._a: unknown[]) => Promise.resolve(json(stats)));
    vi.stubGlobal("fetch", fn);
    expect((await fetchAlertStats()).high_critical_active).toBe(1);
    expect(String(fn.mock.calls[0][0])).toMatch(/\/alerts\/stats$/);
  });
});

describe("AlertLifecyclePanel", () => {
  const buttons = () => screen.queryAllByRole("button").map((b) => b.textContent);

  it("shows only the actions valid for the current status", () => {
    const { rerender } = render(<AlertLifecyclePanel alert={base} onChanged={vi.fn()} />);
    expect(buttons()).toEqual(["Acknowledge", "Start investigating", "Resolve", "Mark false positive"]);
    rerender(<AlertLifecyclePanel alert={withStatus("open", { acknowledged_at: "2026-11-05T11:00:00Z" })} onChanged={vi.fn()} />);
    expect(buttons()).toEqual(["Start investigating", "Resolve", "Mark false positive"]);
    rerender(<AlertLifecyclePanel alert={withStatus("investigating")} onChanged={vi.fn()} />);
    expect(buttons()).toEqual(["Return to open", "Resolve", "Mark false positive"]);
    rerender(<AlertLifecyclePanel alert={withStatus("resolved", { resolution_note: "Fixed it" })} onChanged={vi.fn()} />);
    expect(buttons()).toEqual(["Reopen"]);
    expect(screen.getByText("Fixed it")).toBeTruthy();
    rerender(<AlertLifecyclePanel alert={withStatus("mystery")} onChanged={vi.fn()} />);
    expect(buttons()).toEqual([]);
  });

  it("asks for confirmation and a reason before resolving, and sends nothing until then", () => {
    const fn = vi.fn();
    vi.stubGlobal("fetch", fn);
    render(<AlertLifecyclePanel alert={base} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    expect(fn).not.toHaveBeenCalled();
    expect(screen.getByText("Resolve this alert?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm: Resolve" }));
    expect(screen.getByRole("alert").textContent).toMatch(/reason is required/i);
    fireEvent.change(screen.getByLabelText("Resolution note"), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm: Resolve" }));
    expect(fn).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(buttons()).toContain("Resolve"); // back to the action list
  });

  it("does not report success before the backend confirms, blocks double submits, then reports the confirmed alert", async () => {
    let release: (r: Response) => void = () => undefined;
    const fn = vi.fn((..._a: unknown[]) => new Promise<Response>((resolve) => (release = resolve)));
    vi.stubGlobal("fetch", fn);
    const onChanged = vi.fn();
    render(<AlertLifecyclePanel alert={base} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark false positive" }));
    fireEvent.change(screen.getByLabelText("Why is this a false positive?"), { target: { value: "Scanner" } });
    const confirm = screen.getByRole("button", { name: "Confirm: Mark false positive" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    fireEvent.submit(confirm.closest("form")!);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Saving…" })).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull(); // no success message yet
    expect(onChanged).not.toHaveBeenCalled();

    const updated = withStatus("false_positive", { resolution_note: "Scanner" });
    release(json({ success: true, alert: updated }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(onChanged.mock.calls[0][0]).toEqual(updated);
    expect(screen.getByRole("status").textContent).toBe("Alert is now false positive.");
    expect(JSON.parse(String((fn.mock.calls[0][1] as RequestInit).body))).toEqual({ status: "false_positive", reason: "Scanner" });
  });

  it("shows a backend error, keeps the form for retry and never reports success", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(json({ error: { message: "The alert was changed by someone else. Reload it and try again" } }, 409))));
    const onChanged = vi.fn();
    render(<AlertLifecyclePanel alert={base} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    fireEvent.change(screen.getByLabelText("Resolution note"), { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm: Resolve" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/changed by someone else/));
    expect(onChanged).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
    expect((screen.getByRole("button", { name: "Confirm: Resolve" }) as HTMLButtonElement).disabled).toBe(false); // can retry
  });

  it("moves to investigating directly (no reason needed) and acknowledges with one request each", async () => {
    const fn = vi.fn((..._a: unknown[]) => Promise.resolve(json({ success: true, alert: withStatus("investigating") })));
    vi.stubGlobal("fetch", fn);
    const onChanged = vi.fn();
    render(<AlertLifecyclePanel alert={base} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Start investigating" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((fn.mock.calls[0][1] as RequestInit).body))).toEqual({ status: "investigating" });
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(2));
    expect(String(fn.mock.calls[1][0])).toMatch(/\/alerts\/ALT-1\/acknowledge$/);
  });

  it("requires a reason to reopen", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<AlertLifecyclePanel alert={withStatus("resolved", { resolution_note: "x" })} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Reopen" }));
    expect(screen.getByText("Reopen this alert?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm: Reopen" }));
    expect(screen.getByRole("alert").textContent).toMatch(/required/);
  });
});

describe("StatusTimeline", () => {
  it("shows an empty state", () => {
    render(<StatusTimeline history={[]} />);
    expect(screen.getByText("No lifecycle changes recorded yet.")).toBeTruthy();
  });

  it("lists newest first, shows reasons as plain text and never shows an actor", () => {
    render(
      <StatusTimeline
        history={[
          { action: "acknowledged", previous_status: "open", new_status: "open", timestamp: "2026-11-05T10:00:00Z", reason: null },
          { action: "status_change", previous_status: "open", new_status: "resolved", timestamp: "2026-11-05T11:00:00Z", reason: "<b>done</b>" },
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0].textContent).toContain("resolved");
    expect(items[0].textContent).toContain("<b>done</b>");
    expect(items[1].textContent).toContain("Acknowledged");
    expect(document.querySelector("b")).toBeNull();
  });
});

describe("AlertTable actions", () => {
  const rows = [
    { ...base, alert_id: "A-open" },
    { ...base, alert_id: "A-ack", acknowledged_at: "2026-11-05T11:00:00Z" },
    { ...base, alert_id: "A-res", status: "resolved" },
  ];
  const isDisabled = (name: string) => (screen.getByRole("button", { name }) as HTMLButtonElement).disabled;

  it("enables row shortcuts only where valid and reports the action without selecting the row", () => {
    const onQuick = vi.fn();
    const onSelect = vi.fn();
    render(<AlertTable alerts={rows} selectedId={null} onSelect={onSelect} onQuickAction={onQuick} />);
    expect(isDisabled("Acknowledge alert A-open")).toBe(false);
    expect(isDisabled("Acknowledge alert A-ack")).toBe(true);
    expect(isDisabled("Start investigating alert A-ack")).toBe(false);
    expect(isDisabled("Start investigating alert A-res")).toBe(true);
    expect(screen.getByText("ack")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge alert A-open" }));
    expect(onQuick).toHaveBeenCalledWith(rows[0], "acknowledge");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("disables every shortcut while a request is running and hides the column when read-only", () => {
    const { rerender } = render(<AlertTable alerts={rows} selectedId={null} onSelect={vi.fn()} onQuickAction={vi.fn()} actionsBusy />);
    expect(isDisabled("Acknowledge alert A-open")).toBe(true);
    expect(isDisabled("Start investigating alert A-open")).toBe(true);
    rerender(<AlertTable alerts={rows} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.queryByText("Actions")).toBeNull();
  });
});

describe("AlertDetails integration", () => {
  /** A tiny fake backend: GET /alerts/ID, GET /investigations, PATCH /alerts/ID/status. */
  function fakeBackend(opts: { patchStatus?: number } = {}) {
    let current = base;
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        const path = String(url).replace(/^.*\/api\/v1/, "");
        calls.push(`${init?.method ?? "GET"} ${path}`);
        if (path.startsWith("/investigations")) {
          return Promise.resolve(json({ success: true, page: 1, limit: 20, total: 1, count: 1, investigations: [{ investigation_id: "INV-1", title: "Brute force", status: "in_progress", alert_count: 1, note_count: 0, created_at: "t", updated_at: "t" }] }));
        }
        if (init?.method === "PATCH") {
          if (opts.patchStatus && opts.patchStatus >= 400) return Promise.resolve(json({ error: { message: "An alert that is resolved cannot be changed to investigating" } }, opts.patchStatus));
          current = withStatus("resolved", { resolution_note: "Fixed", status_history: [{ action: "status_change", previous_status: "open", new_status: "resolved", timestamp: "2026-11-05T12:00:00Z", reason: "Fixed" }] });
        }
        return Promise.resolve(json({ success: true, alert: current }));
      }),
    );
    return calls;
  }

  const open = (onChanged = vi.fn()) => {
    render(<MemoryRouter><AlertDetails alertId="ALT-1" onClose={vi.fn()} onChanged={onChanged} /></MemoryRouter>);
    return onChanged;
  };

  it("loads status, history, and the linked investigation with its own status label", async () => {
    fakeBackend();
    open();
    await screen.findByRole("button", { name: "Resolve" });
    expect(screen.getByText("No lifecycle changes recorded yet.")).toBeTruthy();
    const link = await screen.findByRole("link", { name: /Brute force/ });
    expect(link.getAttribute("href")).toBe("/investigations/INV-1");
    expect(screen.getByText("Investigation status")).toBeTruthy();
  });

  it("after a confirmed change it refetches the alert and asks the page to refresh its list and metrics", async () => {
    const calls = fakeBackend();
    const onChanged = open();
    fireEvent.click(await screen.findByRole("button", { name: "Resolve" }));
    fireEvent.change(screen.getByLabelText("Resolution note"), { target: { value: "Fixed" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm: Resolve" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    await screen.findByRole("button", { name: "Reopen" });
    expect(calls.filter((c) => c === "GET /alerts/ALT-1").length).toBe(2); // initial load + refresh after the change
    expect(screen.getByRole("list", { name: /Status history/ }).textContent).toContain("Fixed");
  });

  it("keeps the old state and shows the error when the backend rejects the change", async () => {
    fakeBackend({ patchStatus: 409 });
    const onChanged = open();
    fireEvent.click(await screen.findByRole("button", { name: "Resolve" }));
    fireEvent.change(screen.getByLabelText("Resolution note"), { target: { value: "Fixed" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm: Resolve" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/cannot be changed/));
    expect(onChanged).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull();
  });
});
