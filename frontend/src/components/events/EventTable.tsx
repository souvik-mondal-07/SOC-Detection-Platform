import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";
import type { SecurityEvent } from "../../types/events";

interface EventTableProps {
  events: readonly SecurityEvent[];
  selectedId?: string | null;
  onSelect?: (eventId: string) => void;
  /** Fewer columns, for use on the dashboard. */
  compact?: boolean;
}

const TH = "px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";
const TD = "px-3 py-2 align-top text-sm text-slate-700";

export default function EventTable({ events, selectedId = null, onSelect, compact = false }: EventTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200">
        <caption className="sr-only">Security events, newest first</caption>
        <thead className="bg-slate-50">
          <tr>
            <th scope="col" className={TH}>Time</th>
            <th scope="col" className={TH}>Status</th>
            <th scope="col" className={TH}>Type</th>
            {!compact && <th scope="col" className={TH}>Source</th>}
            {!compact && <th scope="col" className={TH}>Action</th>}
            {!compact && <th scope="col" className={TH}>User</th>}
            <th scope="col" className={TH}>Source IP</th>
            <th scope="col" className={TH}>Message</th>
            {onSelect && <th scope="col" className={TH}><span className="sr-only">Details</span></th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {events.map((event) => (
            <tr
              key={event.event_id}
              className={event.event_id === selectedId ? "bg-teal-50" : onSelect ? "cursor-pointer hover:bg-slate-50" : undefined}
              onClick={onSelect ? () => onSelect(event.event_id) : undefined}
            >
              <td className={`${TD} whitespace-nowrap tabular-nums`}>{formatTimestamp(event.timestamp)}</td>
              <td className={TD}><StatusBadge value={event.status} /></td>
              <td className={TD}>{event.event_type}</td>
              {!compact && <td className={TD}>{event.source}</td>}
              {!compact && <td className={TD}>{event.action}</td>}
              {!compact && <td className={TD}>{event.username ?? "—"}</td>}
              <td className={`${TD} whitespace-nowrap font-mono text-xs`}>{event.source_ip ?? "—"}</td>
              <td className={`${TD} max-w-md truncate`} title={event.message}>{event.message}</td>
              {onSelect && (
                <td className={TD}>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); onSelect(event.event_id); }}
                    aria-label={`View details for event ${event.event_id}`}
                    aria-pressed={event.event_id === selectedId}
                    className="rounded px-2 py-0.5 text-xs font-medium text-accent hover:bg-teal-50 focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    Details
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
