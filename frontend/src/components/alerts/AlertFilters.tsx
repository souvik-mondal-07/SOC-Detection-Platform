import { useState, type FormEvent } from "react";
import { ALERT_SEVERITIES, ALERT_STATUSES, DEFAULT_ALERT_FILTERS, type AlertFilters as Filters } from "../../types/alerts";

interface AlertFiltersProps {
  applied: Filters;
  onApply: (filters: Filters) => void;
}

const FIELD = "field";
const LABEL = "field-label";

/** Returns an error message for obviously invalid input; the backend still validates everything. */
export function validateAlertFilters(f: Filters): string | null {
  const min = f.priority_min === "" ? null : Number(f.priority_min);
  const max = f.priority_max === "" ? null : Number(f.priority_max);
  for (const value of [min, max]) {
    if (value !== null && (!Number.isInteger(value) || value < 0 || value > 100)) return "Priority must be a whole number from 0 to 100.";
  }
  if (min !== null && max !== null && min > max) return "Minimum priority cannot be greater than maximum priority.";
  if (f.rule_id !== "" && !/^[A-Z]{2,10}-\d{3,}$/.test(f.rule_id)) return "Rule ID looks like AUTH-001 (capital letters, a dash, at least 3 digits).";
  return null;
}

export default function AlertFilters({ applied, onApply }: AlertFiltersProps) {
  const [draft, setDraft] = useState<Filters>(applied);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof Filters, value: string) => setDraft((d) => ({ ...d, [key]: value }));
  const isDefault = JSON.stringify(applied) === JSON.stringify(DEFAULT_ALERT_FILTERS) && JSON.stringify(draft) === JSON.stringify(DEFAULT_ALERT_FILTERS);

  function submit(e: FormEvent) {
    e.preventDefault();
    const next = { ...draft, rule_id: draft.rule_id.trim().toUpperCase(), source_ip: draft.source_ip.trim() };
    const problem = validateAlertFilters(next);
    setError(problem);
    if (problem) return;
    setDraft(next);
    onApply(next);
  }

  function reset() {
    setDraft(DEFAULT_ALERT_FILTERS);
    setError(null);
    onApply(DEFAULT_ALERT_FILTERS);
  }

  return (
    <form onSubmit={submit} className="panel p-4" aria-label="Filter alerts">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <div>
          <label htmlFor="a-severity" className={LABEL}>Severity</label>
          <select id="a-severity" className={FIELD} value={draft.severity} onChange={(e) => set("severity", e.target.value)}>
            <option value="">All</option>
            {ALERT_SEVERITIES.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="a-status" className={LABEL}>Status</label>
          <select id="a-status" className={FIELD} value={draft.status} onChange={(e) => set("status", e.target.value)}>
            <option value="">All</option>
            {ALERT_STATUSES.map((v) => <option key={v} value={v}>{v.replace(/_/g, " ")}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="a-rule" className={LABEL}>Rule ID</label>
          <input id="a-rule" className={FIELD} value={draft.rule_id} onChange={(e) => set("rule_id", e.target.value)} placeholder="AUTH-001" autoComplete="off" spellCheck={false} maxLength={32} />
        </div>
        <div>
          <label htmlFor="a-ip" className={LABEL}>Source IP</label>
          <input id="a-ip" className={FIELD} value={draft.source_ip} onChange={(e) => set("source_ip", e.target.value)} placeholder="Exact address" autoComplete="off" spellCheck={false} maxLength={45} />
        </div>
        <div>
          <label htmlFor="a-pmin" className={LABEL}>Priority min</label>
          <input id="a-pmin" type="number" min={0} max={100} step={1} className={FIELD} value={draft.priority_min} onChange={(e) => set("priority_min", e.target.value)} placeholder="0" />
        </div>
        <div>
          <label htmlFor="a-pmax" className={LABEL}>Priority max</label>
          <input id="a-pmax" type="number" min={0} max={100} step={1} className={FIELD} value={draft.priority_max} onChange={(e) => set("priority_max", e.target.value)} placeholder="100" />
        </div>
      </div>
      {error && <p className="mt-3 text-sm text-critical" role="alert">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn-primary">
          Apply filters
        </button>
        <button type="button" onClick={reset} disabled={isDefault} className="btn">
          Reset filters
        </button>
      </div>
    </form>
  );
}
