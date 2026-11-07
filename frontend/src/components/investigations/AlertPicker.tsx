import { useState } from "react";
import { useAlerts } from "../../hooks/useAlerts";
import { ALERT_SEVERITIES, DEFAULT_ALERT_FILTERS } from "../../types/alerts";
import { MAX_LINK_REQUEST_ALERTS } from "../../types/investigations";
import ErrorState from "../common/ErrorState";
import { formatTimestamp } from "../common/format";
import Pagination from "../common/Pagination";
import PriorityScore from "../common/PriorityScore";
import { TableSkeleton } from "../common/Skeleton";
import StateMessage from "../common/StateMessage";
import StatusBadge from "../common/StatusBadge";

interface AlertPickerProps {
  /** Alerts already in the investigation: shown as linked and not selectable. */
  linkedIds?: readonly string[];
  selected: readonly string[];
  onChange: (alertIds: string[]) => void;
  idPrefix: string;
}

/** Choose existing alerts (read from GET /alerts, highest priority first). Selections persist across pages and filters. */
export default function AlertPicker({ linkedIds = [], selected, onChange, idPrefix }: AlertPickerProps) {
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const alerts = useAlerts({ ...DEFAULT_ALERT_FILTERS, severity, page, limit });
  const linked = new Set(linkedIds);
  const atLimit = selected.length >= MAX_LINK_REQUEST_ALERTS;

  function toggle(alertId: string) {
    onChange(selected.includes(alertId) ? selected.filter((id) => id !== alertId) : [...selected, alertId]);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <label htmlFor={`${idPrefix}-severity`} className="field-label">Severity</label>
          <select id={`${idPrefix}-severity`} className="field !w-auto" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
            <option value="">All</option>
            {ALERT_SEVERITIES.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <p className="text-sm text-muted" role="status">
          {selected.length} selected{atLimit ? ` (maximum ${MAX_LINK_REQUEST_ALERTS} per request)` : ""}
        </p>
      </div>

      {alerts.kind === "loading" && <TableSkeleton label="Loading alerts" />}
      {alerts.kind === "error" && <ErrorState title="Could not load alerts" message={alerts.message} onRetry={alerts.reload} />}
      {alerts.kind === "loaded" && alerts.data.alerts.length === 0 && (
        <StateMessage variant="empty" title={severity ? "No alerts match this severity." : "No alerts exist yet."}>
          {severity ? "Choose another severity." : "Alerts appear after detection runs on ingested events."}
        </StateMessage>
      )}
      {alerts.kind === "loaded" && alerts.data.alerts.length > 0 && (
        <>
          <ul className="panel divide-y divide-line/60" aria-label="Alerts to select">
            {alerts.data.alerts.map((alert) => {
              const isLinked = linked.has(alert.alert_id);
              const checked = selected.includes(alert.alert_id);
              const inputId = `${idPrefix}-${alert.alert_id}`;
              return (
                <li key={alert.alert_id} className={`flex items-start gap-3 px-3 py-2 ${isLinked ? "opacity-60" : ""}`}>
                  <input
                    id={inputId}
                    type="checkbox"
                    className="mt-1 h-4 w-4 accent-[var(--color-neon)]"
                    checked={checked}
                    disabled={isLinked || (!checked && atLimit)}
                    onChange={() => toggle(alert.alert_id)}
                  />
                  <label htmlFor={inputId} className="grid min-w-0 flex-1 gap-1 sm:grid-cols-[1fr_auto] sm:items-center">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-fg" title={alert.title}>{alert.title}</span>
                      <span className="block font-mono text-[11px] text-muted">
                        {alert.alert_id} · {alert.source_ip ?? "no source IP"} · {formatTimestamp(alert.created_at)}
                        {isLinked ? " · already linked" : ""}
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      <StatusBadge value={alert.severity} />
                      <PriorityScore score={alert.priority_score} severity={alert.severity} />
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          <Pagination page={page} limit={limit} total={alerts.data.total} onPage={setPage} onLimit={(n) => { setLimit(n); setPage(1); }} />
        </>
      )}
    </div>
  );
}
