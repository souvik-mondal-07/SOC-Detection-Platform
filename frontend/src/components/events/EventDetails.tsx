import { useEvent } from "../../hooks/useEvents";
import { formatTimestamp } from "../common/format";
import StateMessage from "../common/StateMessage";
import StatusBadge from "../common/StatusBadge";

interface EventDetailsProps {
  eventId: string;
  onClose: () => void;
}

/** Loads one event with GET /events/{event_id}. Metadata is rendered as plain text, never as HTML. */
export default function EventDetails({ eventId, onClose }: EventDetailsProps) {
  const state = useEvent(eventId);

  return (
    <aside className="panel p-5" aria-label="Event details">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-mono text-[13px] font-bold uppercase tracking-[0.12em] text-fg">Event details</h2>
        <button
          type="button"
          onClick={onClose}
          className="btn"
        >
          Close
        </button>
      </div>

      {state.kind === "loading" && <p className="mt-4 text-sm text-muted" role="status">Loading event…</p>}
      {state.kind === "error" && (
        <div className="mt-4"><StateMessage variant="error" title="Could not load this event">{state.message}</StateMessage></div>
      )}
      {state.kind === "loaded" && (
        <dl className="mt-4 space-y-3 text-sm">
          {[
            ["Event ID", <span key="id" className="break-all font-mono text-xs">{state.data.event_id}</span>],
            ["Time", formatTimestamp(state.data.timestamp)],
            ["Status", <StatusBadge key="status" value={state.data.status} />],
            ["Event type", state.data.event_type],
            ["Source", state.data.source],
            ["Action", state.data.action],
            ["Username", state.data.username ?? "—"],
            ["Source IP", <span key="ip" className="font-mono text-xs">{state.data.source_ip ?? "—"}</span>],
            ["Message", <span key="msg" className="break-words">{state.data.message}</span>],
            ["Ingested", formatTimestamp(state.data.created_at)],
          ].map(([term, detail], index) => (
            <div key={index} className="grid grid-cols-[6.5rem_1fr] gap-2 border-b border-line/60 pb-2">
              <dt className="text-muted">{term}</dt>
              <dd className="text-fg">{detail}</dd>
            </div>
          ))}
          <div>
            <dt className="text-muted">Metadata</dt>
            <dd className="mt-1">
              {Object.keys(state.data.metadata).length === 0 ? (
                <span className="text-muted">None</span>
              ) : (
                <pre className="max-h-64 overflow-auto rounded bg-panel-2 p-3 text-xs text-fg">
                  {JSON.stringify(state.data.metadata, null, 2)}
                </pre>
              )}
            </dd>
          </div>
        </dl>
      )}
    </aside>
  );
}
