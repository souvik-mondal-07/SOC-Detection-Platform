// Mirrors backend/app/models/alert_management.py and GET /alerts query parameters (backend/app/api/v1/alerts.py).

export const ALERT_SEVERITIES = ["low", "medium", "high", "critical"] as const;
export const ALERT_STATUSES = ["open", "investigating", "resolved", "false_positive"] as const;
export const PAGE_SIZES = [10, 20, 50, 100] as const; // backend maximum for alerts and rules is 100

export interface AlertListItem {
  alert_id: string;
  rule_id: string;
  title: string;
  severity: string;
  priority_score: number;
  priority_reason: string | null;
  status: string;
  source_ip: string | null;
  created_at: string;
}

export interface AlertDetail extends AlertListItem {
  description: string;
  event_ids: string[];
  updated_at: string;
}

export interface AlertListResponse {
  success: boolean;
  page: number;
  limit: number;
  /** Alerts matching the filters across all pages. */
  total: number;
  /** Alerts in this page. */
  count: number;
  alerts: AlertListItem[];
}

export interface AlertResponse {
  success: boolean;
  alert: AlertDetail;
}

/** Query parameters accepted by GET /alerts. Empty string means "not set". Sorting is fixed by the backend (priority desc, newest first). */
export interface AlertFilters {
  severity: string;
  status: string;
  rule_id: string;
  source_ip: string;
  priority_min: string;
  priority_max: string;
}

export interface AlertQuery extends AlertFilters {
  page: number;
  limit: number;
}

export const DEFAULT_ALERT_FILTERS: AlertFilters = {
  severity: "",
  status: "",
  rule_id: "",
  source_ip: "",
  priority_min: "",
  priority_max: "",
};
