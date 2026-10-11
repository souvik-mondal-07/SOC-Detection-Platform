import type { AlertListItem } from "../../types/alerts";
import { formatTimestamp } from "../common/format";
import PriorityScore from "../common/PriorityScore";
import StatusBadge, { SEVERITY_DOT } from "../common/StatusBadge";

interface AlertFeedProps {
  alerts: readonly AlertListItem[];
  selectedId: string | null;
  onSelect: (alertId: string) => void;
}

/** Compact activity rows. Each row opens the same read-only alert details as the Alerts page. */
export default function AlertFeed({ alerts, selectedId, onSelect }: AlertFeedProps) {
  return (
    <ul className="panel divide-y divide-line/60 overflow-hidden" aria-label="Highest-priority alerts">
      {alerts.map((alert) => (
        <li key={alert.alert_id}>
          <button
            type="button"
            onClick={() => onSelect(alert.alert_id)}
            aria-label={`View details for alert ${alert.alert_id}: ${alert.title}`}
            className={`group flex w-full flex-wrap items-center gap-x-4 gap-y-1 py-3 pl-0 pr-4 text-left transition-colors hover:bg-neon/5 ${alert.alert_id === selectedId ? "bg-neon/10" : ""}`}
          >
            <span className={`mr-1 w-1 self-stretch ${Object.hasOwn(SEVERITY_DOT, alert.severity) ? SEVERITY_DOT[alert.severity] : "bg-dim"}`} aria-hidden="true" />
            <span className="min-w-0 flex-1 basis-56">
              <span className="block truncate text-sm font-semibold text-fg group-hover:text-neon">{alert.title}</span>
              <span className="mt-0.5 block font-mono text-[11px] text-muted">
                {alert.alert_id} · {alert.rule_id}
              </span>
            </span>
            <StatusBadge value={alert.severity} />
            <PriorityScore score={alert.priority_score} severity={alert.severity} />
            <span className="w-32 font-mono text-xs text-body">{alert.source_ip ?? "—"}</span>
            <span className="w-44 font-mono text-xs tabular-nums text-muted">{formatTimestamp(alert.created_at)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
