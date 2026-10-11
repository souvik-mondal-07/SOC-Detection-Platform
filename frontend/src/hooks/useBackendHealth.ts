import { fetchHealth } from "../services/api";
import type { HealthResponse } from "../types/health";
import { useAsync } from "./useAsync";

export type BackendState =
  | { kind: "loading" }
  | { kind: "online"; data: HealthResponse }
  | { kind: "offline"; reason: string };

/** Polls GET /health. A "degraded" answer (database down) is still "online": the API itself responded. */
export function useBackendHealth(refreshKey = 0): BackendState {
  const state = useAsync((signal) => fetchHealth(signal), [], { refreshKey });
  // A failed refresh means the backend can no longer be reached, so the indicator must not keep saying "online".
  if (state.kind === "loaded" && state.refreshError) return { kind: "offline", reason: state.refreshError };
  if (state.kind === "loaded") return { kind: "online", data: state.data };
  if (state.kind === "error") return { kind: "offline", reason: state.message };
  return { kind: "loading" };
}
