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
import { useReportUpdated } from "../hooks/useRefresh";
import { DEFAULT_ALERT_FILTERS, type AlertFilters as Filters } from "../types/alerts";

export default function AlertsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_ALERT_FILTERS);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const alerts = useAlerts({ ...filters, page, limit });
  useReportUpdated(alerts.updatedAt);

  const filtered = JSON.stringify(filters) !== JSON.stringify(DEFAULT_ALERT_FILTERS);

  return (
    <>
      <p className="text-sm text-muted">
        Detection alerts, highest priority first (ties: newest first). The backend fixes this order. This view is read-only.
      </p>
      <AlertFilters applied={filters} onApply={(next) => { setFilters(next); setPage(1); }} />

      <section aria-label="Alert list" className="min-w-0 space-y-3">
        <RefreshError errors={[alerts.refreshError]} updatedAt={alerts.updatedAt} onRetry={alerts.reload} />
        {alerts.kind === "loading" && <TableSkeleton label="Loading alerts" />}
        {alerts.kind === "error" && <ErrorState title="Could not load alerts" message={alerts.message} onRetry={alerts.reload} />}
        {alerts.kind === "loaded" && alerts.data.alerts.length === 0 && (
          <StateMessage variant="empty" title={filtered ? "No alerts match these filters." : "No alerts found."}>
            {alerts.data.total > 0 && page > 1 ? (
              <button type="button" onClick={() => setPage(1)} className="font-medium text-cyan hover:underline">Go to the first page</button>
            ) : filtered ? (
              "Try widening or resetting the filters."
            ) : (
              "Alerts appear here after detection runs on ingested events."
            )}
          </StateMessage>
        )}
        {alerts.kind === "loaded" && alerts.data.alerts.length > 0 && (
          <>
            <AlertTable alerts={alerts.data.alerts} selectedId={selectedId} onSelect={setSelectedId} />
            <Pagination page={page} limit={limit} total={alerts.data.total} onPage={setPage} onLimit={(n) => { setLimit(n); setPage(1); }} />
          </>
        )}
      </section>

      {selectedId && <AlertDetails alertId={selectedId} onClose={() => setSelectedId(null)} />}
    </>
  );
}
