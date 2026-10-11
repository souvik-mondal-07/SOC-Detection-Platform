import { useRule } from "../../hooks/useRules";
import DetailDrawer from "../common/DetailDrawer";
import DetailList from "../common/DetailList";
import ErrorState from "../common/ErrorState";
import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";

/** Read-only view of GET /rules/{id}. Conditions are shown as plain text; editing belongs to a later step. */
export default function RuleDetails({ ruleId, onClose }: { ruleId: string; onClose: () => void }) {
  const state = useRule(ruleId);
  return (
    <DetailDrawer title={`Rule ${ruleId}`} onClose={onClose}>
      {state.kind === "loading" && <p className="text-sm text-muted" role="status">Loading rule…</p>}
      {state.kind === "error" && <ErrorState title="Could not load this rule" message={state.message} onRetry={state.reload} />}
      {state.kind === "loaded" && (
        <div className="space-y-5">
          <h3 className="text-lg font-semibold text-fg">{state.data.name}</h3>
          <DetailList
            rows={[
              ["Severity", <StatusBadge key="s" value={state.data.severity} />],
              ["State", <StatusBadge key="e" value={state.data.enabled ? "enabled" : "disabled"} />],
              ["Category", state.data.category],
              ["Description", state.data.description || "—"],
              ["Created", formatTimestamp(state.data.created_at)],
              ["Updated", formatTimestamp(state.data.updated_at)],
            ]}
          />
          <section aria-label="Conditions">
            <h4 className="text-sm font-semibold text-fg">Conditions</h4>
            <pre className="mt-2 max-h-96 overflow-auto rounded bg-panel-2 p-3 text-xs text-fg">{JSON.stringify(state.data.conditions, null, 2)}</pre>
          </section>
        </div>
      )}
    </DetailDrawer>
  );
}
