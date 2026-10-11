import { fetchAlerts, fetchEvents, fetchRules } from "../services/api";
import { ALERT_SEVERITIES, ALERT_STATUSES, DEFAULT_ALERT_FILTERS, type AlertListItem, type AlertQuery } from "../types/alerts";
import type { SecurityEvent } from "../types/events";
import { useAsync } from "./useAsync";
import { useRefreshKey } from "./useRefresh";

const ONE: Pick<AlertQuery, "page" | "limit"> = { page: 1, limit: 1 };
const SAMPLE_PAGE_SIZE = 100;
/** The alert API has no aggregation or time-range endpoint, so the trend chart reads at most this many pages. */
export const MAX_ALERT_SAMPLE_PAGES = 5;
/** GET /events accepts at most 500 and has no total or paging. */
export const EVENT_SAMPLE_LIMIT = 500;

export interface AlertCounts {
  total: number;
  bySeverity: Record<string, number>;
  byStatus: Record<string, number>;
}

/** Exact counts: every number is the `total` field the API reports for a filtered request (limit=1). */
export function useAlertCounts() {
  return useAsync(
    async (signal): Promise<AlertCounts> => {
      const query = (filters: Partial<typeof DEFAULT_ALERT_FILTERS>): AlertQuery => ({ ...DEFAULT_ALERT_FILTERS, ...filters, ...ONE });
      const [all, ...rest] = await Promise.all([
        fetchAlerts(query({}), signal),
        ...ALERT_SEVERITIES.map((severity) => fetchAlerts(query({ severity }), signal)),
        ...ALERT_STATUSES.map((status) => fetchAlerts(query({ status }), signal)),
      ]);
      const bySeverity: Record<string, number> = {};
      const byStatus: Record<string, number> = {};
      ALERT_SEVERITIES.forEach((name, i) => (bySeverity[name] = rest[i].total));
      ALERT_STATUSES.forEach((name, i) => (byStatus[name] = rest[ALERT_SEVERITIES.length + i].total));
      return { total: all.total, bySeverity, byStatus };
    },
    [],
    { refreshKey: useRefreshKey() },
  );
}

export interface AlertSample {
  alerts: AlertListItem[];
  total: number;
}

/** Highest-priority alerts first (the API's fixed order), up to MAX_ALERT_SAMPLE_PAGES pages. Used only for the trend chart. */
export function useAlertSample() {
  return useAsync(
    async (signal): Promise<AlertSample> => {
      const query = (page: number): AlertQuery => ({ ...DEFAULT_ALERT_FILTERS, page, limit: SAMPLE_PAGE_SIZE });
      const first = await fetchAlerts(query(1), signal);
      const pages = Math.min(MAX_ALERT_SAMPLE_PAGES, Math.ceil(first.total / SAMPLE_PAGE_SIZE));
      const more = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, i) => fetchAlerts(query(i + 2), signal)));
      return { alerts: [first, ...more].flatMap((p) => p.alerts), total: first.total };
    },
    [],
    { refreshKey: useRefreshKey() },
  );
}

export interface EventSample {
  events: SecurityEvent[];
  /** True when the API returned fewer events than the limit, which means it returned every stored event. */
  complete: boolean;
}

export function useEventSample() {
  return useAsync(
    async (signal): Promise<EventSample> => {
      const result = await fetchEvents({ source: "", event_type: "", status: "", source_ip: "", limit: EVENT_SAMPLE_LIMIT }, signal);
      return { events: result.events, complete: result.events.length < EVENT_SAMPLE_LIMIT };
    },
    [],
    { refreshKey: useRefreshKey() },
  );
}

export function useRuleCounts() {
  return useAsync(
    async (signal) => {
      const base = { page: 1, limit: 1, category: "", severity: "", enabled: "" as const, name: "" };
      const [all, enabled] = await Promise.all([fetchRules(base, signal), fetchRules({ ...base, enabled: "true" }, signal)]);
      return { total: all.total, enabled: enabled.total };
    },
    [],
    { refreshKey: useRefreshKey() },
  );
}
