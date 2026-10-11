import { useState, type FormEvent } from "react";
import { ALERT_SEVERITIES } from "../../types/alerts";
import { DEFAULT_RULE_FILTERS, RULE_CATEGORIES, type RuleFilters as Filters } from "../../types/rules";

const FIELD = "field";
const LABEL = "field-label";

export default function RuleFilters({ applied, onApply }: { applied: Filters; onApply: (f: Filters) => void }) {
  const [draft, setDraft] = useState<Filters>(applied);
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const submit = (e: FormEvent) => { e.preventDefault(); onApply({ ...draft, name: draft.name.trim() }); };
  const reset = () => { setDraft(DEFAULT_RULE_FILTERS); onApply(DEFAULT_RULE_FILTERS); };

  return (
    <form onSubmit={submit} className="panel p-4" aria-label="Filter detection rules">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label htmlFor="r-name" className={LABEL}>Name contains</label>
          <input id="r-name" className={FIELD} value={draft.name} onChange={(e) => set("name", e.target.value)} maxLength={120} autoComplete="off" />
        </div>
        <div>
          <label htmlFor="r-cat" className={LABEL}>Category</label>
          <select id="r-cat" className={FIELD} value={draft.category} onChange={(e) => set("category", e.target.value)}>
            <option value="">All</option>
            {RULE_CATEGORIES.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="r-sev" className={LABEL}>Severity</label>
          <select id="r-sev" className={FIELD} value={draft.severity} onChange={(e) => set("severity", e.target.value)}>
            <option value="">All</option>
            {ALERT_SEVERITIES.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="r-en" className={LABEL}>State</label>
          <select id="r-en" className={FIELD} value={draft.enabled} onChange={(e) => set("enabled", e.target.value as Filters["enabled"])}>
            <option value="">All</option>
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn-primary">Apply filters</button>
        <button type="button" onClick={reset} className="btn">Reset filters</button>
      </div>
    </form>
  );
}
