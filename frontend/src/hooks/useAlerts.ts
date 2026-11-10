import { fetchAlert, fetchAlerts, fetchInvestigationsForAlert } from "../services/api";
import type { AlertQuery } from "../types/alerts";
import { useAsync } from "./useAsync";
import { useRefreshKey } from "./useRefresh";

export function useAlerts(query: AlertQuery) {
  const { page, limit, severity, status, rule_id, source_ip, priority_min, priority_max } = query;
  return useAsync((signal) => fetchAlerts(query, signal), [page, limit, severity, status, rule_id, source_ip, priority_min, priority_max], {
    refreshKey: useRefreshKey(),
  });
}

export function useAlert(alertId: string) {
  return useAsync((signal) => fetchAlert(alertId, signal), [alertId]);
}

/** Investigations that reference one alert. Reloaded on every refresh so a newly linked investigation appears. */
export function useAlertInvestigations(alertId: string) {
  return useAsync((signal) => fetchInvestigationsForAlert(alertId, signal), [alertId]);
}
