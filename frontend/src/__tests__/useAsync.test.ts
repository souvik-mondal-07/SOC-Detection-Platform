// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useAsync } from "../hooks/useAsync";

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe("useAsync", () => {
  it("keeps loaded data, shows a separate refresh error and keeps the old timestamp when a refresh fails; retry recovers", async () => {
    let call = 0;
    const load = async () => {
      call += 1;
      if (call === 2) throw new Error("backend down");
      return `data-${call}`;
    };
    const { result, rerender } = renderHook(({ key }) => useAsync(load, ["same"], { refreshKey: key }), { initialProps: { key: 0 } });

    await waitFor(() => expect(result.current.kind).toBe("loaded"));
    const firstUpdate = result.current.updatedAt;
    expect(firstUpdate).not.toBeNull();
    expect(result.current.kind === "loaded" && result.current.data).toBe("data-1");

    await new Promise((r) => setTimeout(r, 5));
    rerender({ key: 1 }); // silent refresh that fails
    await waitFor(() => expect(result.current.refreshError).toBe("backend down"));
    expect(result.current.kind).toBe("loaded"); // not replaced by a blocking error
    expect(result.current.kind === "loaded" && result.current.data).toBe("data-1");
    expect(result.current.updatedAt).toBe(firstUpdate);
    expect(result.current.refreshing).toBe(false);

    act(() => result.current.reload()); // retry succeeds
    await waitFor(() => expect(result.current.refreshError).toBeNull());
    expect(result.current.kind === "loaded" && result.current.data).toBe("data-3");
    expect(result.current.updatedAt!.getTime()).toBeGreaterThan(firstUpdate!.getTime());
  });

  it("reports an initial-load failure as an error, not as a refresh error", async () => {
    const { result } = renderHook(() => useAsync(async () => { throw new Error("nope"); }, []));
    await waitFor(() => expect(result.current.kind).toBe("error"));
    expect(result.current.refreshError).toBeNull();
    expect(result.current.updatedAt).toBeNull();
  });

  it("resets to loading when the deps change instead of showing the old query's data", async () => {
    const gate = deferred<string>();
    const { result, rerender } = renderHook(
      ({ q }) => useAsync((signal) => (q === "a" ? Promise.resolve("A") : (signal.addEventListener("abort", () => undefined), gate.promise)), [q]),
      { initialProps: { q: "a" } },
    );
    await waitFor(() => expect(result.current.kind).toBe("loaded"));
    rerender({ q: "b" });
    await waitFor(() => expect(result.current.kind).toBe("loading"));
    expect(result.current.updatedAt).toBeNull();
    act(() => gate.resolve("B"));
    await waitFor(() => expect(result.current.kind === "loaded" && result.current.data).toBe("B"));
  });

  it("aborts the previous request when a new one starts and ignores AbortError", async () => {
    const signals: AbortSignal[] = [];
    const load = (signal: AbortSignal) => {
      signals.push(signal);
      return new Promise<string>((_, reject) => signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
    };
    const { result, rerender } = renderHook(({ q }) => useAsync(load, [q]), { initialProps: { q: "a" } });
    rerender({ q: "b" });
    expect(signals[0].aborted).toBe(true);
    expect(signals.at(-1)!.aborted).toBe(false);
    await act(async () => { await new Promise((r) => setTimeout(r, 5)); });
    expect(result.current.kind).toBe("loading"); // the aborted request did not become an error
    expect(result.current.refreshError).toBeNull();
  });
});
