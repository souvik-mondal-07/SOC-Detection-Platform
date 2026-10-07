import { Link } from "react-router-dom";
import { useEvents } from "../../hooks/useEvents";
import { DEFAULT_EVENT_FILTERS } from "../../types/events";
import StateMessage from "../common/StateMessage";
import EventTable from "../events/EventTable";

const RECENT = { ...DEFAULT_EVENT_FILTERS, limit: 5 };

/** The newest stored events, straight from GET /events. */
export default function RecentEventsPanel() {
  const events = useEvents(RECENT);

  return (
    <section aria-labelledby="recent-heading" className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="recent-heading" className="text-base font-semibold text-ink">Recent security events</h2>
        <Link to="/security-events" className="text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent">
          View all events
        </Link>
      </div>
      {events.kind === "loading" && <StateMessage variant="loading" title="Loading recent events…" />}
      {events.kind === "error" && <StateMessage variant="error" title="Could not load recent events">{events.message}</StateMessage>}
      {events.kind === "loaded" && events.data.events.length === 0 && (
        <StateMessage variant="empty" title="No security events found.">Ingest events through the API to see them here.</StateMessage>
      )}
      {events.kind === "loaded" && events.data.events.length > 0 && <EventTable events={events.data.events} compact />}
    </section>
  );
}
