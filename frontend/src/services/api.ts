import type { EventFilters, EventListResponse, SecurityEvent } from "../types/events";
import type { HealthResponse } from "../types/health";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Error with a message that is safe to show. Messages come from the backend's {"error": {...}} shape. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** The configured API address without any credentials, query or fragment, safe to display. */
export function getApiBaseUrlForDisplay(): string {
  try {
    const url = new URL(API_BASE_URL);
    return `${url.origin}${url.pathname.replace(/\/$/, "")}`;
  } catch {
    return "(invalid VITE_API_BASE_URL)";
  }
}

interface BackendErrorBody {
  error?: { message?: unknown; details?: unknown };
}

async function describeFailure(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as BackendErrorBody;
    const message = typeof body.error?.message === "string" ? body.error.message : null;
    const details = Array.isArray(body.error?.details)
      ? (body.error.details as unknown[])
          .map((item) => {
            const detail = item as { field?: unknown; message?: unknown };
            return typeof detail.message === "string" ? `${typeof detail.field === "string" ? `${detail.field}: ` : ""}${detail.message}` : null;
          })
          .filter((text): text is string => text !== null)
      : [];
    if (message) return details.length > 0 ? `${message} (${details.join("; ")})` : message;
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return `Backend responded with status ${response.status}`;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status);
  }
  return response.json() as Promise<T>;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health", signal);
}

/** GET /events: newest first, only the filters the backend supports. */
export function fetchEvents(filters: EventFilters, signal?: AbortSignal): Promise<EventListResponse> {
  const params = new URLSearchParams({ limit: String(filters.limit) });
  for (const key of ["source", "event_type", "status", "source_ip"] as const) {
    const value = filters[key].trim();
    if (value) params.set(key, value);
  }
  return getJson<EventListResponse>(`/events?${params.toString()}`, signal);
}

/** GET /events/{event_id} */
export function fetchEvent(eventId: string, signal?: AbortSignal): Promise<SecurityEvent> {
  return getJson<SecurityEvent>(`/events/${encodeURIComponent(eventId)}`, signal);
}
