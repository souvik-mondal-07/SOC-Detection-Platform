import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import EventDetails from "../components/events/EventDetails";
import EventFilters from "../components/events/EventFilters";
import EventTable from "../components/events/EventTable";
import RefreshError from "../components/common/RefreshError";
import StateMessage from "../components/common/StateMessage";
import ErrorState from "../components/common/ErrorState";
import { TableSkeleton } from "../components/common/Skeleton";
import { useEvents } from "../hooks/useEvents";
import { useReportUpdated } from "../hooks/useRefresh";
import { DEFAULT_EVENT_FILTERS, type EventFilters as Filters } from "../types/events";

export default function SecurityEventsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_EVENT_FILTERS);
  // ?event=<id> deep-links from the alert details panel.
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedId, setSelected] = useState<string | null>(searchParams.get("event"));
  const setSelectedId = (id: string | null) => {
    setSelected(id);
    setSearchParams(id ? { event: id } : {}, { replace: true });
  };
  const events = useEvents(filters);
  useReportUpdated(events.updatedAt);

  return (
    <>
      <p className="text-sm text-muted">
        Normalized events stored by the backend, newest first. The API supports exact-match filters and a result limit but
        not paging, so this page loads the newest events up to the limit you choose.
      </p>

      <EventFilters applied={filters} onApply={(next) => { setFilters(next); setSelectedId(null); }} />

      <div className={selectedId ? "grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]" : undefined}>
        <section aria-label="Event list" className="min-w-0 space-y-3">
          <RefreshError errors={[events.refreshError]} updatedAt={events.updatedAt} onRetry={events.reload} />
          {events.kind === "loading" && <TableSkeleton label="Loading security events" />}
          {events.kind === "error" && <ErrorState title="Could not load security events" message={events.message} onRetry={events.reload} />}
          {events.kind === "loaded" && events.data.events.length === 0 && (
            <StateMessage variant="empty" title="No security events found.">
              No stored events match the current filters.
            </StateMessage>
          )}
          {events.kind === "loaded" && events.data.events.length > 0 && (
            <>
              <p className="text-sm text-muted" role="status">
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
