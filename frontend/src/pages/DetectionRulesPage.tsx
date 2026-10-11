import { useState } from "react";
import ErrorState from "../components/common/ErrorState";
import Pagination from "../components/common/Pagination";
import { TableSkeleton } from "../components/common/Skeleton";
import RefreshError from "../components/common/RefreshError";
import StateMessage from "../components/common/StateMessage";
import RuleDetails from "../components/rules/RuleDetails";
import RuleFilters from "../components/rules/RuleFilters";
import RuleTable from "../components/rules/RuleTable";
import { useReportUpdated } from "../hooks/useRefresh";
import { useRules } from "../hooks/useRules";
import { DEFAULT_RULE_FILTERS, type RuleFilters as Filters } from "../types/rules";

export default function DetectionRulesPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_RULE_FILTERS);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const rules = useRules({ ...filters, page, limit });
  useReportUpdated(rules.updatedAt);

  return (
    <>
      <p className="text-sm text-muted">
        Detection rules stored in the backend. This view is read-only: creating, editing, enabling and deleting rules is planned for a later step.
      </p>
      <RuleFilters applied={filters} onApply={(next) => { setFilters(next); setPage(1); }} />
      <section aria-label="Rule list" className="min-w-0 space-y-3">
        <RefreshError errors={[rules.refreshError]} updatedAt={rules.updatedAt} onRetry={rules.reload} />
        {rules.kind === "loading" && <TableSkeleton label="Loading detection rules" />}
        {rules.kind === "error" && <ErrorState title="Could not load detection rules" message={rules.message} onRetry={rules.reload} />}
        {rules.kind === "loaded" && rules.data.rules.length === 0 && (
          <StateMessage variant="empty" title="No detection rules found.">
            {rules.data.total > 0 && page > 1 ? (
              <button type="button" onClick={() => setPage(1)} className="font-medium text-cyan hover:underline">Go to the first page</button>
            ) : (
              "No rules match the current filters. Seed the initial rules with scripts/seed_detection_rules.py."
            )}
          </StateMessage>
        )}
        {rules.kind === "loaded" && rules.data.rules.length > 0 && (
          <>
            <RuleTable rules={rules.data.rules} selectedId={selectedId} onSelect={setSelectedId} />
            <Pagination page={page} limit={limit} total={rules.data.total} onPage={setPage} onLimit={(n) => { setLimit(n); setPage(1); }} />
          </>
        )}
      </section>
      {selectedId && <RuleDetails ruleId={selectedId} onClose={() => setSelectedId(null)} />}
    </>
  );
}
