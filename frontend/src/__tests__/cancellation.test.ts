import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchAlerts, isAbortError } from "../services/api";
import { DEFAULT_ALERT_FILTERS } from "../types/alerts";

const body = JSON.stringify({ success: true, page: 1, limit: 1, total: 0, count: 0, alerts: [] });
let counter = 0;
/** A distinct URL per test so shared in-flight requests from other tests cannot interfere. */
const query = () => ({ ...DEFAULT_ALERT_FILTERS, rule_id: `TEST-${String(++counter).padStart(3, "0")}`, page: 1, limit: 1 });

interface Pending {
  signal: AbortSignal | null | undefined;
  finish: () => void;
}

/** fetch stub that stays pending until finish() is called, and rejects with AbortError when its signal aborts. */
function pendingFetch() {
  const calls: Pending[] = [];
  const fn = vi.fn((_url: unknown, init?: RequestInit) => {
    return new Promise<Response>((resolve, reject) => {
      const signal = init?.signal;
      signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      calls.push({ signal, finish: () => resolve(new Response(body)) });
    });
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

afterEach(() => vi.unstubAllGlobals());

describe("request cancellation", () => {
  it("passes an AbortSignal to fetch and aborts it when the only consumer aborts", async () => {
    const { fn, calls } = pendingFetch();
    const controller = new AbortController();
    const promise = fetchAlerts(query(), controller.signal);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(calls[0].signal).toBeInstanceOf(AbortSignal);
    expect(calls[0].signal?.aborted).toBe(false);
    controller.abort();
    const error = await promise.catch((e: unknown) => e);
    expect(isAbortError(error)).toBe(true);
    expect(error).not.toBeInstanceOf(ApiError);
    expect(calls[0].signal?.aborted).toBe(true);
  });

  it("does not cancel a shared request while another consumer still needs it", async () => {
    const { fn, calls } = pendingFetch();
    const q = query();
    const first = new AbortController();
    const second = new AbortController();
    const a = fetchAlerts(q, first.signal);
    const b = fetchAlerts(q, second.signal);
    expect(fn).toHaveBeenCalledTimes(1);

    first.abort();
    expect(isAbortError(await a.catch((e: unknown) => e))).toBe(true);
    expect(calls[0].signal?.aborted).toBe(false); // consumer b still waits for it

    calls[0].finish();
    expect((await b).total).toBe(0);
  });

  it("cancels the shared request once every consumer has aborted, and a later call starts a fresh one", async () => {
    const { fn, calls } = pendingFetch();
    const q = query();
    const first = new AbortController();
    const second = new AbortController();
    const a = fetchAlerts(q, first.signal).catch((e: unknown) => e);
    const b = fetchAlerts(q, second.signal).catch((e: unknown) => e);
    first.abort();
    second.abort();
    expect(isAbortError(await a)).toBe(true);
    expect(isAbortError(await b)).toBe(true);
    expect(calls[0].signal?.aborted).toBe(true);

    const c = fetchAlerts(q);
    expect(fn).toHaveBeenCalledTimes(2);
    calls[1].finish();
    expect((await c).total).toBe(0);
  });

  it("rejects immediately with AbortError for an already aborted signal, without calling fetch", async () => {
    const { fn } = pendingFetch();
    const controller = new AbortController();
    controller.abort();
    expect(isAbortError(await fetchAlerts(query(), controller.signal).catch((e: unknown) => e))).toBe(true);
    expect(fn).not.toHaveBeenCalled();
  });
});
