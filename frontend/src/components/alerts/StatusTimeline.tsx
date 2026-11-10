import type { StatusHistoryEntry } from "../../types/alerts";
import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";

/**
 * Lifecycle history, newest first (the API sends oldest first). No actor is shown because authentication does not exist yet,
 * so the backend cannot attribute a change to anyone.
 */
export default function StatusTimeline({ history }: { history: readonly StatusHistoryEntry[] }) {
  if (history.length === 0) return <p className="mt-1 text-sm text-muted">No lifecycle changes recorded yet.</p>;
  const newestFirst = [...history].reverse();
  return (
    <ol className="mt-2 space-y-3 border-l border-line pl-4" aria-label="Status history, newest first">
      {newestFirst.map((entry, i) => (
        <li key={`${entry.timestamp}-${i}`} className="relative text-sm">
          <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-neon" aria-hidden="true" />
          {entry.action === "acknowledged" ? (
            <p className="font-medium text-fg">Acknowledged</p>
          ) : (
            <p className="flex flex-wrap items-center gap-1.5 text-fg">
              <StatusBadge value={entry.previous_status} />
              <span aria-label="changed to">→</span>
              <StatusBadge value={entry.new_status} />
            </p>
          )}
          <p className="mt-0.5 font-mono text-[11px] tabular-nums text-muted">{formatTimestamp(entry.timestamp)}</p>
          {entry.reason && <p className="mt-1 whitespace-pre-wrap break-words text-body">{entry.reason}</p>}
        </li>
      ))}
    </ol>
  );
}
