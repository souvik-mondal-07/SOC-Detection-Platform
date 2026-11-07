import { useState } from "react";
import type { LinkedAlert } from "../../types/investigations";
import { formatTimestamp } from "../common/format";
import PriorityScore from "../common/PriorityScore";
import StatusBadge from "../common/StatusBadge";

interface Props {
  alerts: readonly LinkedAlert[];
  busy: boolean;
  onUnlink: (alertId: string) => void;
}

function AlertCard({ alert, canUnlink, busy, onUnlink }: { alert: LinkedAlert; canUnlink: boolean; busy: boolean; onUnlink: (id: string) => void }) {
  const [confirming, setConfirming] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? alert.event_ids : alert.event_ids.slice(0, 5);
  return (
    <li className="panel space-y-2 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-fg">{alert.available ? alert.title : "Alert unavailable"}</p>
          <p className="font-mono text-[11px] text-muted">{alert.alert_id}{alert.rule_id ? ` · ${alert.rule_id}` : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          {alert.available && alert.severity && <StatusBadge value={alert.severity} />}
          {alert.available && alert.priority_score !== null && <PriorityScore score={alert.priority_score} severity={alert.severity ?? ""} />}
        </div>
      </div>
      {alert.available ? (
        <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
          <div><dt className="tech-label">Alert status</dt><dd className="mt-0.5">{alert.status ? <StatusBadge value={alert.status} /> : "—"}</dd></div>
          <div><dt className="tech-label">Source IP</dt><dd className="mt-0.5 font-mono text-fg">{alert.source_ip ?? "—"}</dd></div>
          <div><dt className="tech-label">Created</dt><dd className="mt-0.5 font-mono text-fg">{formatTimestamp(alert.created_at)}</dd></div>
        </dl>
      ) : (
        <p className="text-xs text-muted">This alert no longer exists in the alerts collection. You can unlink it.</p>
      )}
      {alert.available && (
        <div>
          <p className="tech-label">Associated events ({alert.event_count})</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {shown.map((id) => <li key={id} className="rounded bg-panel-2 px-1.5 py-0.5 font-mono text-[11px] text-cyan">{id}</li>)}
          </ul>
          {alert.event_ids.length > 5 && (
            <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-1 text-xs font-medium text-cyan hover:underline focus-visible:outline-2 focus-visible:outline-neon">
              {showAll ? "Show fewer" : `Show ${alert.event_ids.length - 5} more`}
            </button>
          )}
          {alert.event_count > alert.event_ids.length && <p className="mt-1 text-xs text-muted">Showing the first {alert.event_ids.length} of {alert.event_count} events.</p>}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {!confirming ? (
          <button type="button" className="btn" disabled={busy || !canUnlink} onClick={() => setConfirming(true)} title={canUnlink ? undefined : "An investigation must keep at least one alert"} aria-label={`Unlink alert ${alert.alert_id}`}>
            Unlink
          </button>
        ) : (
          <>
            <span className="text-xs text-muted">Remove the link only. The alert is not changed.</span>
            <button type="button" className="btn-primary" disabled={busy} onClick={() => { setConfirming(false); onUnlink(alert.alert_id); }} aria-label={`Confirm unlink alert ${alert.alert_id}`}>Confirm unlink</button>
            <button type="button" className="btn" onClick={() => setConfirming(false)}>Cancel</button>
          </>
        )}
      </div>
    </li>
  );
}

export default function LinkedAlertsPanel({ alerts, busy, onUnlink }: Props) {
  return (
    <ul className="space-y-3" aria-label="Linked alerts">
      {alerts.map((alert) => <AlertCard key={alert.alert_id} alert={alert} canUnlink={alerts.length > 1} busy={busy} onUnlink={onUnlink} />)}
    </ul>
  );
}
