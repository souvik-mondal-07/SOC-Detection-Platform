import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import CreateInvestigationForm from "../components/investigations/CreateInvestigationForm";
import InvestigationTable from "../components/investigations/InvestigationTable";
import ErrorState from "../components/common/ErrorState";
import Pagination from "../components/common/Pagination";
import RefreshError from "../components/common/RefreshError";
import { TableSkeleton } from "../components/common/Skeleton";
import StateMessage from "../components/common/StateMessage";
import { useInvestigations } from "../hooks/useInvestigations";
import { useReportUpdated } from "../hooks/useRefresh";
import { DEFAULT_INVESTIGATION_FILTERS, INVESTIGATION_STATUSES, STATUS_LABELS, type InvestigationFilters } from "../types/investigations";

export default function InvestigationsPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<InvestigationFilters>(DEFAULT_INVESTIGATION_FILTERS);
  const [titleDraft, setTitleDraft] = useState("");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [creating, setCreating] = useState(false);
  const list = useInvestigations({ ...filters, page, limit });
  useReportUpdated(list.updatedAt);

  const filtered = filters.status !== "" || filters.title !== "";

  function applyTitle(e: FormEvent) {
    e.preventDefault();
    setFilters((f) => ({ ...f, title: titleDraft.trim() }));
    setPage(1);
  }

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-3xl text-sm text-muted">
          Investigations group the alerts an analyst is working on, with notes and a status. Investigation status is separate from alert status. There is no authentication yet, so this is for local development only.
        </p>
        {!creating && <button type="button" className="btn-primary" onClick={() => setCreating(true)}>New investigation</button>}
      </div>

      {creating && (
        <CreateInvestigationForm
          onCancel={() => setCreating(false)}
          onCreated={(inv) => navigate(`/investigations/${encodeURIComponent(inv.investigation_id)}`)}
        />
      )}

      <form onSubmit={applyTitle} className="panel p-4" aria-label="Filter investigations">
        <div className="grid gap-3 sm:grid-cols-[12rem_1fr_auto] sm:items-end">
          <div>
            <label htmlFor="inv-status" className="field-label">Status</label>
            <select id="inv-status" className="field" value={filters.status} onChange={(e) => { setFilters((f) => ({ ...f, status: e.target.value })); setPage(1); }}>
              <option value="">All</option>
              {INVESTIGATION_STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="inv-search" className="field-label">Title contains</label>
            <input id="inv-search" className="field" value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} maxLength={100} autoComplete="off" placeholder="Search titles" />
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary">Apply</button>
            <button type="button" className="btn" disabled={!filtered && titleDraft === ""} onClick={() => { setFilters(DEFAULT_INVESTIGATION_FILTERS); setTitleDraft(""); setPage(1); }}>Reset</button>
          </div>
        </div>
      </form>

      <section aria-label="Investigation list" className="min-w-0 space-y-3">
        <RefreshError errors={[list.refreshError]} updatedAt={list.updatedAt} onRetry={list.reload} />
        {list.kind === "loading" && <TableSkeleton label="Loading investigations" />}
        {list.kind === "error" && <ErrorState title="Could not load investigations" message={list.message} onRetry={list.reload} />}
        {list.kind === "loaded" && list.data.investigations.length === 0 && (
          <StateMessage variant="empty" title={filtered ? "No investigations match these filters." : "No investigations yet."}>
            {list.data.total > 0 && page > 1 ? (
              <button type="button" onClick={() => setPage(1)} className="font-medium text-cyan hover:underline">Go to the first page</button>
            ) : filtered ? (
              "Try widening or resetting the filters."
            ) : (
              "Use “New investigation” to start one from existing alerts."
            )}
          </StateMessage>
        )}
        {list.kind === "loaded" && list.data.investigations.length > 0 && (
          <>
            <InvestigationTable investigations={list.data.investigations} />
            <Pagination page={page} limit={limit} total={list.data.total} onPage={setPage} onLimit={(n) => { setLimit(n); setPage(1); }} />
          </>
        )}
      </section>
    </>
  );
}
