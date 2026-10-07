import { fetchEvent, fetchEvents } from "../services/api";
import type { EventFilters } from "../types/events";
import { useAsync } from "./useAsync";

export function useEvents(filters: EventFilters) {
  const { source, event_type, status, source_ip, limit } = filters;
  return useAsync((signal) => fetchEvents(filters, signal), [source, event_type, status, source_ip, limit]);
}

export function useEvent(eventId: string) {
  return useAsync((signal) => fetchEvent(eventId, signal), [eventId]);
}
