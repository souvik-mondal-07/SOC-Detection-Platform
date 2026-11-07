import { fetchInvestigation, fetchInvestigations } from "../services/api";
import type { InvestigationQuery } from "../types/investigations";
import { useAsync } from "./useAsync";
import { useRefreshKey } from "./useRefresh";

export function useInvestigations(query: InvestigationQuery) {
  const { page, limit, status, title } = query;
  return useAsync((signal) => fetchInvestigations(query, signal), [page, limit, status, title], { refreshKey: useRefreshKey() });
}

export function useInvestigation(id: string) {
  return useAsync((signal) => fetchInvestigation(id, signal), [id], { refreshKey: useRefreshKey() });
}
