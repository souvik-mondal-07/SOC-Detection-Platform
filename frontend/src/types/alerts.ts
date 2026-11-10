// Mirrors backend/app/models/alert_management.py and GET /alerts query parameters (backend/app/api/v1/alerts.py).

export const ALERT_SEVERITIES = ["low", "medium", "high", "critical"] as const;
export const ALERT_STATUSES = ["open", "investigating", "resolved", "false_positive"] as const;
export type AlertStatus = (typeof ALERT_STATUSES)[number];
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
  /** Set when an analyst acknowledged the alert. Acknowledgement is not a status: the alert stays "open". */
  acknowledged_at?: string | null;
}

/** One audit entry. oldest first in AlertDetail.status_history. There is no actor: authentication does not exist yet. */
export interface StatusHistoryEntry {
  action: string; // "status_change" | "acknowledged"
  previous_status: string;
  new_status: string;
  timestamp: string;
  reason: string | null;
}

export interface AlertDetail extends AlertListItem {
  description: string;
  event_ids: string[];
  updated_at: string;
  resolution_note?: string | null;
  status_history: StatusHistoryEntry[];
}

/** GET /alerts/stats: exact counts computed by the backend over all alerts. */
export interface AlertStats {
  success: boolean;
  total: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  active: number;
  high_critical_active: number;
  acknowledged_open: number;
}

// -- Lifecycle (Step 12). Same table as backend app/models/alert.py ALLOWED_TRANSITIONS; the backend enforces it. --

export const STATUS_REASON_MAX = 1000;

export const ALERT_TRANSITIONS: Readonly<Record<AlertStatus, readonly AlertStatus[]>> = {
  open: ["investigating", "resolved", "false_positive"],
  investigating: ["open", "resolved", "false_positive"],
  resolved: ["open"],
  false_positive: ["open"],
};

export interface TransitionAction {
  to: AlertStatus;
  label: string;
  /** Needs a written reason and an explicit confirmation step. */
  needsReason: boolean;
  reasonLabel: string;
  tone: "primary" | "default";
}

/** Whether closing (resolved / false positive) or reopening a closed alert; both need a reason (backend reason_required). */
export function transitionAction(from: AlertStatus, to: AlertStatus): TransitionAction {
  const closed = from === "resolved" || from === "false_positive";
  if (closed) return { to, label: "Reopen", needsReason: true, reasonLabel: "Reason for reopening", tone: "default" };
  if (to === "resolved") return { to, label: "Resolve", needsReason: true, reasonLabel: "Resolution note", tone: "primary" };
  if (to === "false_positive") return { to, label: "Mark false positive", needsReason: true, reasonLabel: "Why is this a false positive?", tone: "default" };
  if (to === "investigating") return { to, label: "Start investigating", needsReason: false, reasonLabel: "Note (optional)", tone: "primary" };
  return { to, label: "Return to open", needsReason: false, reasonLabel: "Note (optional)", tone: "default" };
}

export function isAlertStatus(value: string): value is AlertStatus {
  return (ALERT_STATUSES as readonly string[]).includes(value);
}

/** Actions offered for a status. An unknown status (untrusted backend data) offers nothing. */
export function availableActions(status: string): TransitionAction[] {
  return isAlertStatus(status) ? ALERT_TRANSITIONS[status].map((to) => transitionAction(status, to)) : [];
}

export function canAcknowledge(alert: { status: string; acknowledged_at?: string | null }): boolean {
  return alert.status === "open" && !alert.acknowledged_at;
}

export function validateReason(text: string, required: boolean): string | null {
  const value = text.trim();
  if (required && value === "") return "A reason is required.";
  if (value.length > STATUS_REASON_MAX) return `The reason can have at most ${STATUS_REASON_MAX} characters.`;
  return null;
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
