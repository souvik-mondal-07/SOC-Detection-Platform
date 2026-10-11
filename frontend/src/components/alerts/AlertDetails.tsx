import { useState } from "react";
import { Link } from "react-router-dom";
import { useAlert } from "../../hooks/useAlerts";
import DetailDrawer from "../common/DetailDrawer";
import DetailList from "../common/DetailList";
import ErrorState from "../common/ErrorState";
import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";

const EVENT_PREVIEW = 25;

/** Read-only. Loads GET /alerts/{id} because the list response has no description or event IDs. */
export default function AlertDetails({ alertId, onClose }: { alertId: string; onClose: () => void }) {
  const state = useAlert(alertId);
  const [showAll, setShowAll] = useState(false);

  return (
    <DetailDrawer title={`Alert ${alertId}`} onClose={onClose}>
      {state.kind === "loading" && <p className="text-sm text-muted" role="status">Loading alert…</p>}
      {state.kind === "error" && <ErrorState title="Could not load this alert" message={state.message} onRetry={state.reload} />}
      {state.kind === "loaded" && (() => {
        const alert = state.data;
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
                ["Status", <StatusBadge key="st" value={alert.status} />],
                ["Description", alert.description || "—"],
                ["Rule ID", <span key="r" className="font-mono text-xs">{alert.rule_id}</span>],
                ["Source IP", <span key="ip" className="font-mono text-xs">{alert.source_ip ?? "—"}</span>],
                ["Created", formatTimestamp(alert.created_at)],
                ["Updated", formatTimestamp(alert.updated_at)],
              ]}
            />
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
