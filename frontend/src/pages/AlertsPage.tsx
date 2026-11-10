import { useState } from "react";
import AlertDetails from "../components/alerts/AlertDetails";
import AlertFilters from "../components/alerts/AlertFilters";
import AlertTable from "../components/alerts/AlertTable";
import ErrorState from "../components/common/ErrorState";
import Pagination from "../components/common/Pagination";
import { TableSkeleton } from "../components/common/Skeleton";
import RefreshError from "../components/common/RefreshError";
import StateMessage from "../components/common/StateMessage";
import { useAlerts } from "../hooks/useAlerts";
import type { QuickAction } from "../components/alerts/AlertRowActions";
import { useLayoutContext, useReportUpdated } from "../hooks/useRefresh";
import { acknowledgeAlert, changeAlertStatus } from "../services/api";
import { DEFAULT_ALERT_FILTERS, type AlertFilters as Filters, type AlertListItem } from "../types/alerts";

export default function AlertsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_ALERT_FILTERS);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const alerts = useAlerts({ ...filters, page, limit });
  useReportUpdated(alerts.updatedAt);
  const { refresh } = useLayoutContext();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  /** Row shortcuts. The notice and the refresh happen only after the backend has answered. */
  async function quickAction(alert: AlertListItem, action: QuickAction) {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    try {
      if (action === "acknowledge") await acknowledgeAlert(alert.alert_id);
      else await changeAlertStatus(alert.alert_id, "investigating");
      setNotice({ kind: "success", text: action === "acknowledge" ? `Alert ${alert.alert_id} acknowledged.` : `Alert ${alert.alert_id} is now investigating.` });
      refresh();
    } catch (err) {
      setNotice({ kind: "error", text: `Alert ${alert.alert_id}: ${err instanceof Error ? err.message : "the change could not be saved."}` });
    } finally {
      setBusy(false);
    }
  }

  const filtered = JSON.stringify(filters) !== JSON.stringify(DEFAULT_ALERT_FILTERS);

  return (
    <>
      <p className="text-sm text-muted">
        Detection alerts, highest priority first (ties: newest first). The backend fixes this order. Acknowledge or investigate from the table; open an alert to resolve it, mark it as a false positive, reopen it or read its history.
      </p>
      <AlertFilters applied={filters} onApply={(next) => { setFilters(next); setPage(1); }} />

      <section aria-label="Alert list" className="min-w-0 space-y-3">
        {notice && (
          <div className={`flex items-start justify-between gap-3 rounded border px-3 py-2 text-sm ${notice.kind === "success" ? "border-neon/40 text-neon" : "border-critical/50 text-critical"}`} role={notice.kind === "error" ? "alert" : "status"}>
            <span>{notice.text}</span>
            <button type="button" onClick={() => setNotice(null)} className="font-medium hover:underline" aria-label="Dismiss message">Dismiss</button>
          </div>
        )}
        <RefreshError errors={[alerts.refreshError]} updatedAt={alerts.updatedAt} onRetry={alerts.reload} />
        {alerts.kind === "loading" && <TableSkeleton label="Loading alerts" />}
        {alerts.kind === "error" && <ErrorState title="Could not load alerts" message={alerts.message} onRetry={alerts.reload} />}
        {alerts.kind === "loaded" && alerts.data.alerts.length === 0 && (
          <StateMessage variant="empty" title={filtered ? "No alerts match these filters." : "No alerts found."}>
            {alerts.data.total > 0 && page > 1 ? (
              <button type="button" onClick={() => setPage(1)} className="font-medium text-cyan hover:underline">Go to the first page</button>
            ) : filtered ? (
              "Try widening or resetting the filters, for example by choosing a different status."
            ) : (
              "Alerts appear here after detection runs on ingested events."
            )}
          </StateMessage>
        )}
        {alerts.kind === "loaded" && alerts.data.alerts.length > 0 && (
          <>
            <AlertTable alerts={alerts.data.alerts} selectedId={selectedId} onSelect={setSelectedId} onQuickAction={quickAction} actionsBusy={busy} />
            <Pagination page={page} limit={limit} total={alerts.data.total} onPage={setPage} onLimit={(n) => { setLimit(n); setPage(1); }} />
          </>
        )}
      </section>

      {selectedId && <AlertDetails alertId={selectedId} onClose={() => setSelectedId(null)} onChanged={refresh} />}
    </>
  );
}
