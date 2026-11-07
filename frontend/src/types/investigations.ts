// Mirrors backend/app/models/investigation_management.py and the /investigations routes.
// Investigation status is separate from alert status. The API has no authentication yet (local development only).

export const INVESTIGATION_STATUSES = ["open", "in_progress", "closed"] as const;
export type InvestigationStatus = (typeof INVESTIGATION_STATUSES)[number];

/** Same table as backend ALLOWED_TRANSITIONS. The backend enforces it; the UI only offers these choices. */
export const STATUS_TRANSITIONS: Readonly<Record<InvestigationStatus, readonly InvestigationStatus[]>> = {
  open: ["in_progress", "closed"],
  in_progress: ["open", "closed"],
  closed: ["in_progress"],
};

export const STATUS_LABELS: Readonly<Record<InvestigationStatus, string>> = {
  open: "Open",
  in_progress: "In progress",
  closed: "Closed",
};

export const MAX_TITLE_LENGTH = 200;
export const MAX_NOTE_LENGTH = 2000;
export const MAX_LINK_REQUEST_ALERTS = 100;

export interface InvestigationListItem {
  investigation_id: string;
  title: string;
  status: string;
  alert_count: number;
  note_count: number;
  created_at: string;
  updated_at: string;
}

export interface InvestigationNote {
  note_id: string;
  text: string;
  created_at: string;
}

/** Live context for one linked alert. When available is false the alert no longer exists and only alert_id is set. */
export interface LinkedAlert {
  alert_id: string;
  available: boolean;
  rule_id: string | null;
  title: string | null;
  severity: string | null;
  priority_score: number | null;
  status: string | null;
  source_ip: string | null;
  created_at: string | null;
  event_count: number;
  /** First 50 only; event_count has the full number. */
  event_ids: string[];
}

export interface InvestigationDetail extends InvestigationListItem {
  alert_ids: string[];
  alerts: LinkedAlert[];
  /** Oldest first. */
  notes: InvestigationNote[];
  unavailable_alert_count: number;
}

export interface InvestigationListResponse {
  success: boolean;
  page: number;
  limit: number;
  total: number;
  count: number;
  investigations: InvestigationListItem[];
}

export interface InvestigationResponse {
  success: boolean;
  investigation: InvestigationDetail;
}

export interface InvestigationFilters {
  status: string;
  title: string;
}

export interface InvestigationQuery extends InvestigationFilters {
  page: number;
  limit: number;
}

export const DEFAULT_INVESTIGATION_FILTERS: InvestigationFilters = { status: "", title: "" };

/** Client-side checks that mirror the backend limits. The backend validates everything again. */
export function validateTitle(title: string): string | null {
  const text = title.trim();
  if (text === "") return "Enter a title.";
  if (text.length > MAX_TITLE_LENGTH) return `The title can have at most ${MAX_TITLE_LENGTH} characters.`;
  return null;
}

export function validateNote(text: string): string | null {
  const value = text.trim();
  if (value === "") return "Write a note before adding it.";
  if (value.length > MAX_NOTE_LENGTH) return `A note can have at most ${MAX_NOTE_LENGTH} characters.`;
  return null;
}
