import type { RuleSummary } from "../../types/rules";
import StatusBadge from "../common/StatusBadge";

const TH = "px-3 py-2.5 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-muted";
const TD = "px-3 py-2 align-top text-sm text-body";

export default function RuleTable({ rules, selectedId, onSelect }: { rules: readonly RuleSummary[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <div className="panel overflow-x-auto">
      <table className="min-w-full divide-y divide-line">
        <caption className="sr-only">Detection rules</caption>
        <thead className="bg-panel-2">
          <tr>
            <th scope="col" className={TH}>Rule ID</th>
            <th scope="col" className={TH}>Name</th>
            <th scope="col" className={TH}>Category</th>
            <th scope="col" className={TH}>Severity</th>
            <th scope="col" className={TH}>State</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line/60">
          {rules.map((rule) => (
            <tr key={rule.rule_id} onClick={() => onSelect(rule.rule_id)} className={`cursor-pointer ${rule.rule_id === selectedId ? "bg-neon/10" : "hover:bg-neon/5"}`}>
              <td className={`${TD} whitespace-nowrap font-mono text-xs text-cyan`}>{rule.rule_id}</td>
              <td className={TD}>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onSelect(rule.rule_id); }}
                  aria-label={`View details for rule ${rule.rule_id}: ${rule.name}`}
                  className="text-left font-semibold text-fg hover:text-neon hover:underline focus-visible:outline-2 focus-visible:outline-neon"
                >
                  {rule.name}
                </button>
              </td>
              <td className={TD}><span className="rounded border border-cyan/30 bg-cyan/10 px-1.5 py-0.5 font-mono text-[11px] text-cyan">{rule.category}</span></td>
              <td className={TD}><StatusBadge value={rule.severity} /></td>
              <td className={TD}><StatusBadge value={rule.enabled ? "enabled" : "disabled"} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
