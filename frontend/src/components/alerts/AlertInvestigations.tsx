import { Link } from "react-router-dom";
import { useAlertInvestigations } from "../../hooks/useAlerts";
import StatusBadge from "../common/StatusBadge";

/** Investigations that reference this alert. Their status is the investigation's own and is unrelated to the alert status. */
export default function AlertInvestigations({ alertId }: { alertId: string }) {
  const state = useAlertInvestigations(alertId);
  return (
    <section aria-label="Linked investigations">
      <h4 className="text-sm font-semibold text-fg">Linked investigations</h4>
      {state.kind === "loading" && <p className="mt-1 text-sm text-muted" role="status">Loading investigations…</p>}
      {state.kind === "error" && (
        <p className="mt-1 text-sm text-critical" role="alert">
          Could not load linked investigations ({state.message}).{" "}
          <button type="button" onClick={state.reload} className="font-medium text-cyan hover:underline">Retry</button>
        </p>
      )}
      {state.kind === "loaded" && state.data.investigations.length === 0 && <p className="mt-1 text-sm text-muted">This alert is not part of any investigation.</p>}
      {state.kind === "loaded" && state.data.investigations.length > 0 && (
        <>
          <ul className="mt-2 space-y-2">
            {state.data.investigations.map((inv) => (
              <li key={inv.investigation_id} className="flex flex-wrap items-center justify-between gap-2 rounded bg-panel-2 px-3 py-2 text-sm">
                <Link to={`/investigations/${encodeURIComponent(inv.investigation_id)}`} className="min-w-0 truncate font-medium text-cyan hover:underline focus-visible:outline-2 focus-visible:outline-neon" title={inv.title}>
                  <span className="font-mono text-xs text-muted">{inv.investigation_id}</span> {inv.title}
                </Link>
                <span className="flex items-center gap-1.5 text-xs text-muted">Investigation status <StatusBadge value={inv.status} /></span>
              </li>
            ))}
          </ul>
          {state.data.total > state.data.investigations.length && (
            <p className="mt-1 text-xs text-muted">Showing {state.data.investigations.length} of {state.data.total}.</p>
          )}
        </>
      )}
    </section>
  );
}
