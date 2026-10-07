import { useState } from "react";
import EventDetails from "../components/events/EventDetails";
import EventFilters from "../components/events/EventFilters";
import EventTable from "../components/events/EventTable";
import StateMessage from "../components/common/StateMessage";
import { useEvents } from "../hooks/useEvents";
import { DEFAULT_EVENT_FILTERS, type EventFilters as Filters } from "../types/events";

export default function SecurityEventsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_EVENT_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const events = useEvents(filters);

  return (
    <>
      <p className="text-sm text-slate-600">
        Normalized events stored by the backend, newest first. The API supports exact-match filters and a result limit but
        not paging, so this page loads the newest events up to the limit you choose.
      </p>

      <EventFilters applied={filters} onApply={(next) => { setFilters(next); setSelectedId(null); }} />

      <div className={selectedId ? "grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]" : undefined}>
        <section aria-label="Event list" className="min-w-0 space-y-3">
          {events.kind === "loading" && <StateMessage variant="loading" title="Loading security events…" />}
          {events.kind === "error" && (
            <StateMessage variant="error" title="Could not load security events">
              {events.message}
              <div className="mt-3">
                <button type="button" onClick={events.reload} className="rounded-md border border-red-300 bg-white px-3 py-1 text-sm font-medium text-critical hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-critical">
                  Try again
                </button>
              </div>
            </StateMessage>
          )}
          {events.kind === "loaded" && events.data.events.length === 0 && (
            <StateMessage variant="empty" title="No security events found.">
              No stored events match the current filters.
            </StateMessage>
          )}
          {events.kind === "loaded" && events.data.events.length > 0 && (
            <>
              <p className="text-sm text-slate-600" role="status">
                Showing {events.data.count} event{events.data.count === 1 ? "" : "s"}
                {events.data.count === filters.limit ? ` (limit reached; older matching events may exist)` : ""}.
              </p>
              <EventTable events={events.data.events} selectedId={selectedId} onSelect={setSelectedId} />
            </>
          )}
        </section>

        {selectedId && <EventDetails eventId={selectedId} onClose={() => setSelectedId(null)} />}
      </div>
    </>
  );
}
