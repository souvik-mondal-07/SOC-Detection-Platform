import { useEffect, useRef, useState } from "react";
import { isAbortError } from "../services/api";

export type AsyncState<T> =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; data: T };

export interface UseAsyncOptions {
  /** Changing this re-runs the request without resetting to "loading" (silent refresh). */
  refreshKey?: number;
}

export interface AsyncExtras {
  reload: () => void;
  /** True while a silent refresh is running. */
  refreshing: boolean;
  /** Time of the last *successful* response for the current deps; unchanged by failed refreshes. */
  updatedAt: Date | null;
  /** Set when a silent refresh failed after data had loaded. The previous data stays in `data`. Separate from an initial-load `error`. */
  refreshError: string | null;
}

/**
 * Runs `load` on mount and whenever `deps` change. Each new run aborts the previous one (the abort reaches the real fetch),
 * so requests never overlap. Changing `deps` starts a fresh load. A refresh (`refreshKey` or `reload`) keeps the loaded data on
 * screen: if it fails, the data and `updatedAt` are kept and `refreshError` is set instead of replacing the page with an error.
 */
export function useAsync<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: readonly (string | number | boolean | null | undefined)[],
  { refreshKey = 0 }: UseAsyncOptions = {},
): AsyncState<T> & AsyncExtras {
  const [state, setState] = useState<AsyncState<T>>({ kind: "loading" });
  const [version, setVersion] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const loadRef = useRef(load);
  loadRef.current = load;
  const lastDeps = useRef<string | null>(null);
  const hasData = useRef(false);
  const depsKey = JSON.stringify(deps);

  useEffect(() => {
    const controller = new AbortController();
    const silent = lastDeps.current === depsKey && hasData.current;
    lastDeps.current = depsKey;
    if (silent) {
      setRefreshing(true);
    } else {
      hasData.current = false;
      setState({ kind: "loading" });
      setUpdatedAt(null);
      setRefreshError(null);
      setRefreshing(false);
    }
    loadRef.current(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        hasData.current = true;
        setState({ kind: "loaded", data });
        setUpdatedAt(new Date());
        setRefreshError(null);
        setRefreshing(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isAbortError(err)) return; // cancellation is not a failure
        const message = err instanceof Error ? err.message : "Unknown error";
        if (hasData.current) setRefreshError(message);
        else setState({ kind: "error", message });
        setRefreshing(false);
      });
    return () => controller.abort();
  }, [depsKey, refreshKey, version]);

  return { ...state, reload: () => setVersion((n) => n + 1), refreshing, updatedAt, refreshError };
}
