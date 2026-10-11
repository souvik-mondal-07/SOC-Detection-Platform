import { useState, type FormEvent } from "react";
import {
  DEFAULT_EVENT_FILTERS,
  EVENT_LIMITS,
  EVENT_SOURCES,
  EVENT_STATUSES,
  EVENT_TYPES,
  type EventFilters as Filters,
} from "../../types/events";

interface EventFiltersProps {
  applied: Filters;
  onApply: (filters: Filters) => void;
}

const FIELD = "field";
const LABEL = "field-label";

function label(value: string): string {
  return value.replace(/_/g, " ");
}

export default function EventFilters({ applied, onApply }: EventFiltersProps) {
  const [draft, setDraft] = useState<Filters>(applied);
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) => setDraft((current) => ({ ...current, [key]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    onApply({ ...draft, source_ip: draft.source_ip.trim() });
  }

  function reset() {
    setDraft(DEFAULT_EVENT_FILTERS);
    onApply(DEFAULT_EVENT_FILTERS);
  }

  return (
    <form onSubmit={submit} className="panel p-4" aria-label="Filter security events">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label htmlFor="f-type" className={LABEL}>Event type</label>
          <select id="f-type" className={FIELD} value={draft.event_type} onChange={(e) => set("event_type", e.target.value)}>
            <option value="">All</option>
            {EVENT_TYPES.map((v) => <option key={v} value={v}>{label(v)}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-status" className={LABEL}>Status</label>
          <select id="f-status" className={FIELD} value={draft.status} onChange={(e) => set("status", e.target.value)}>
            <option value="">All</option>
            {EVENT_STATUSES.map((v) => <option key={v} value={v}>{label(v)}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-source" className={LABEL}>Source</label>
          <select id="f-source" className={FIELD} value={draft.source} onChange={(e) => set("source", e.target.value)}>
            <option value="">All</option>
            {EVENT_SOURCES.map((v) => <option key={v} value={v}>{label(v)}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-ip" className={LABEL}>Source IP</label>
          <input id="f-ip" className={FIELD} value={draft.source_ip} onChange={(e) => set("source_ip", e.target.value)}
            inputMode="text" autoComplete="off" spellCheck={false} maxLength={45} placeholder="Exact address" />
        </div>
        <div>
          <label htmlFor="f-limit" className={LABEL}>Newest events to load</label>
          <select id="f-limit" className={FIELD} value={draft.limit} onChange={(e) => set("limit", Number(e.target.value))}>
            {EVENT_LIMITS.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn-primary">
          Apply filters
        </button>
        <button type="button" onClick={reset} className="btn">
          Reset
        </button>
      </div>
    </form>
  );
}
