// Mirrors the backend SecurityEvent / EventQuery models (backend/app/models/event.py).

export interface SecurityEvent {
  event_id: string;
  timestamp: string;
  source: string;
  event_type: string;
  action: string;
  status: string;
  username: string | null;
  source_ip: string | null;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface EventListResponse {
  count: number;
  events: SecurityEvent[];
}

/** Filters supported by GET /events. Empty string means "not set". The backend has no offset or page parameter. */
export interface EventFilters {
  source: string;
  event_type: string;
  status: string;
  source_ip: string;
  limit: number;
}

// Allowed filter values defined by the backend enums (not data).
export const EVENT_SOURCES = ["linux_auth", "windows_event", "web_application", "network", "application"] as const;
export const EVENT_TYPES = ["authentication", "web", "network", "privilege", "system", "application"] as const;
export const EVENT_STATUSES = ["success", "failed", "blocked", "unknown"] as const;
export const EVENT_LIMITS = [25, 50, 100, 250, 500] as const; // backend maximum is 500

export const DEFAULT_EVENT_FILTERS: EventFilters = { source: "", event_type: "", status: "", source_ip: "", limit: 50 };
