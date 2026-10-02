import { useEffect, useState } from "react";
import { fetchHealth } from "../services/api";
import type { HealthResponse } from "../types/health";

export type BackendState =
  | { kind: "loading" }
  | { kind: "online"; data: HealthResponse }
  | { kind: "offline"; reason: string };

export function useBackendHealth(): BackendState {
  const [state, setState] = useState<BackendState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((data) => setState({ kind: "online", data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ kind: "offline", reason: err instanceof Error ? err.message : "Unknown error" });
      });
    return () => controller.abort();
  }, []);

  return state;
}
