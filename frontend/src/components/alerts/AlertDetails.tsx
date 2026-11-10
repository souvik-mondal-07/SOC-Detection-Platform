import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAlert } from "../../hooks/useAlerts";
import DetailDrawer from "../common/DetailDrawer";
import DetailList from "../common/DetailList";
import ErrorState from "../common/ErrorState";
import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";
import type { AlertDetail } from "../../types/alerts";
import AlertInvestigations from "./AlertInvestigations";
import AlertLifecyclePanel from "./AlertLifecyclePanel";
import StatusTimeline from "./StatusTimeline";

const EVENT_PREVIEW = 25;

interface Props {
  alertId: string;
  onClose: () => void;
  /** Called after the backend confirmed a lifecycle change, so the page can refresh its list and dashboard metrics. */
  onChanged?: () => void;
}

/** Loads GET /alerts/{id} because the list response has no description, event IDs or history. Hosts the lifecycle controls. */
export default function AlertDetails({ alertId, onClose, onChanged }: Props) {
  const state = useAlert(alertId);
  const [showAll, setShowAll] = useState(false);
  // The alert exactly as the backend returned it after a change; shown until the follow-up reload arrives.
  const [confirmed, setConfirmed] = useState<AlertDetail | null>(null);
  const { updatedAt, reload } = state;
  useEffect(() => setConfirmed(null), [alertId, updatedAt]);

  return (
    <DetailDrawer title={`Alert ${alertId}`} onClose={onClose}>
      {state.kind === "loading" && <p className="text-sm text-muted" role="status">Loading alert…</p>}
      {state.kind === "error" && <ErrorState title="Could not load this alert" message={state.message} onRetry={state.reload} />}
      {state.kind === "loaded" && (() => {
        const alert = confirmed && confirmed.alert_id === state.data.alert_id ? confirmed : state.data;
        const ids = Array.isArray(alert.event_ids) ? alert.event_ids : [];
        const shown = showAll ? ids : ids.slice(0, EVENT_PREVIEW);
        return (
          <div className="space-y-5">
            <h3 className="text-lg font-semibold text-fg">{alert.title}</h3>
            <DetailList
              rows={[
                ["Severity", <StatusBadge key="s" value={alert.severity} />],
                ["Priority score", <span key="p" className="font-semibold tabular-nums">{alert.priority_score} / 100</span>],
                ["Priority reason", alert.priority_reason ?? "—"],
                ["Description", alert.description || "—"],
                ["Rule ID", <span key="r" className="font-mono text-xs">{alert.rule_id}</span>],
                ["Source IP", <span key="ip" className="font-mono text-xs">{alert.source_ip ?? "—"}</span>],
                ["Created", formatTimestamp(alert.created_at)],
                ["Updated", formatTimestamp(alert.updated_at)],
              ]}
            />
            <AlertLifecyclePanel
              alert={alert}
              onChanged={(updated) => {
                setConfirmed(updated);
                reload();
                onChanged?.();
              }}
            />
            <section aria-label="Status history">
              <h4 className="text-sm font-semibold text-fg">Status history</h4>
              <StatusTimeline history={alert.status_history} />
            </section>
            <AlertInvestigations alertId={alert.alert_id} />
            <section aria-label="Associated events">
              <h4 className="text-sm font-semibold text-fg">Associated events ({ids.length})</h4>
              {ids.length === 0 ? (
                <p className="mt-1 text-sm text-muted">None recorded.</p>
              ) : (
                <>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {shown.map((id) => (
                      <li key={id}>
                        <Link
                          to={`/security-events?event=${encodeURIComponent(id)}`}
                          className="rounded bg-panel-2 px-2 py-1 font-mono text-xs text-cyan hover:underline focus-visible:outline-2 focus-visible:outline-neon"
                        >
                          {id}
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {ids.length > EVENT_PREVIEW && (
                    <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-2 text-sm font-medium text-cyan hover:underline focus-visible:outline-2 focus-visible:outline-neon">
                      {showAll ? "Show fewer" : `Show all ${ids.length}`}
                    </button>
                  )}
                </>
              )}
            </section>
          </div>
        );
      })()}
    </DetailDrawer>
  );
}
