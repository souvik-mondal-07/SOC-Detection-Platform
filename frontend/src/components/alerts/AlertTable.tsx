import type { AlertListItem } from "../../types/alerts";
import AlertRowActions, { type QuickAction } from "./AlertRowActions";
import { formatTimestamp } from "../common/format";
import PriorityScore from "../common/PriorityScore";
import StatusBadge, { SEVERITY_EDGE } from "../common/StatusBadge";

interface AlertTableProps {
  alerts: readonly AlertListItem[];
  selectedId: string | null;
  onSelect: (alertId: string) => void;
  /** Optional lifecycle shortcuts (acknowledge / start investigating). Omitted where the table is read-only. */
  onQuickAction?: (alert: AlertListItem, action: QuickAction) => void;
  actionsBusy?: boolean;
}

const TH = "px-3 py-2.5 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-muted";
const TD = "px-3 py-2 align-top text-sm text-body";

export default function AlertTable({ alerts, selectedId, onSelect, onQuickAction, actionsBusy = false }: AlertTableProps) {
  return (
    <div className="panel overflow-x-auto">
      <table className="min-w-full divide-y divide-line">
        <caption className="sr-only">Alerts, highest priority first</caption>
        <thead className="bg-panel-2">
          <tr>
            <th scope="col" className={TH}>Alert ID</th>
            <th scope="col" className={TH}>Title</th>
            <th scope="col" className={TH}>Severity</th>
            <th scope="col" className={TH}>Priority</th>
            <th scope="col" className={TH}>Status</th>
            <th scope="col" className={TH}>Source IP</th>
            <th scope="col" className={TH}>Rule</th>
            <th scope="col" className={TH}>Created</th>
            {onQuickAction && <th scope="col" className={TH}>Actions</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-line/60">
          {alerts.map((alert) => (
            <tr
              key={alert.alert_id}
              onClick={() => onSelect(alert.alert_id)}
              className={`cursor-pointer ${alert.alert_id === selectedId ? "bg-neon/10" : "hover:bg-neon/5"}`}
            >
              <td className={`${TD} whitespace-nowrap font-mono text-xs text-body ${Object.hasOwn(SEVERITY_EDGE, alert.severity) ? SEVERITY_EDGE[alert.severity] : ""}`}>{alert.alert_id}</td>
              <td className={`${TD} max-w-xs`}>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onSelect(alert.alert_id); }}
                  aria-label={`View details for alert ${alert.alert_id}: ${alert.title}`}
                  className="max-w-full truncate text-left font-semibold text-fg hover:text-neon hover:underline focus-visible:outline-2 focus-visible:outline-neon"
                  title={alert.title}
                >
                  {alert.title}
                </button>
              </td>
              <td className={TD}><StatusBadge value={alert.severity} /></td>
              <td className={TD}><PriorityScore score={alert.priority_score} severity={alert.severity} /></td>
              <td className={TD}>
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge value={alert.status} />
                  {alert.status === "open" && alert.acknowledged_at && <span className="font-mono text-[10px] uppercase tracking-wider text-muted" title={`Acknowledged ${formatTimestamp(alert.acknowledged_at)}`}>ack</span>}
                </div>
              </td>
              <td className={`${TD} whitespace-nowrap font-mono text-xs text-fg`}>{alert.source_ip ?? "—"}</td>
              <td className={`${TD} whitespace-nowrap font-mono text-xs text-cyan`}>{alert.rule_id}</td>
              <td className={`${TD} whitespace-nowrap font-mono text-xs tabular-nums text-muted`}>{formatTimestamp(alert.created_at)}</td>
              {onQuickAction && <td className={TD}><AlertRowActions alert={alert} busy={actionsBusy} onAction={onQuickAction} /></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
