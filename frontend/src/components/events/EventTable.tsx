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

const TH = "px-3 py-2.5 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-muted";
const TD = "px-3 py-2 align-top text-sm text-body";

export default function EventTable({ events, selectedId = null, onSelect, compact = false }: EventTableProps) {
  return (
    <div className="panel overflow-x-auto">
      <table className="min-w-full divide-y divide-line">
        <caption className="sr-only">Security events, newest first</caption>
        <thead className="bg-panel-2">
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
        <tbody className="divide-y divide-line/60">
          {events.map((event) => (
            <tr
              key={event.event_id}
              className={event.event_id === selectedId ? "bg-neon/10" : onSelect ? "cursor-pointer hover:bg-neon/5" : undefined}
              onClick={onSelect ? () => onSelect(event.event_id) : undefined}
            >
              <td className={`${TD} whitespace-nowrap font-mono text-xs tabular-nums text-muted`}>{formatTimestamp(event.timestamp)}</td>
              <td className={TD}><StatusBadge value={event.status} /></td>
              <td className={TD}><span className="rounded border border-cyan/30 bg-cyan/10 px-1.5 py-0.5 font-mono text-[11px] text-cyan">{event.event_type}</span></td>
              {!compact && <td className={TD}><span className="rounded border border-line-strong bg-panel-2 px-1.5 py-0.5 font-mono text-[11px] text-body">{event.source}</span></td>}
              {!compact && <td className={`${TD} font-mono text-xs`}>{event.action}</td>}
              {!compact && <td className={`${TD} font-mono text-xs`}>{event.username ?? "—"}</td>}
              <td className={`${TD} whitespace-nowrap font-mono text-xs text-fg`}>{event.source_ip ?? "—"}</td>
              <td className={`${TD} max-w-md truncate`} title={event.message}>{event.message}</td>
              {onSelect && (
                <td className={TD}>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); onSelect(event.event_id); }}
                    aria-label={`View details for event ${event.event_id}`}
                    aria-pressed={event.event_id === selectedId}
                    className="rounded px-2 py-0.5 text-xs font-medium text-cyan hover:bg-neon/10 focus-visible:outline-2 focus-visible:outline-neon"
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
