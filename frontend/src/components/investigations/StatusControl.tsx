import { useState } from "react";
import { STATUS_LABELS, STATUS_TRANSITIONS, type InvestigationStatus } from "../../types/investigations";
import StatusBadge from "../common/StatusBadge";

interface Props {
  status: string;
  busy: boolean;
  onChange: (status: InvestigationStatus) => void;
}

const isKnown = (s: string): s is InvestigationStatus => Object.hasOwn(STATUS_TRANSITIONS, s);

/** Shows the current investigation status and only the allowed next statuses. This does not change any alert status. */
export default function StatusControl({ status, busy, onChange }: Props) {
  const options = isKnown(status) ? STATUS_TRANSITIONS[status] : [];
  const [next, setNext] = useState<string>("");
  const selected = options.includes(next as InvestigationStatus) ? next : "";
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <p className="field-label">Investigation status</p>
        <div className="mt-1"><StatusBadge value={status} /></div>
      </div>
      <div>
        <label htmlFor="inv-next-status" className="field-label">Change to</label>
        <select id="inv-next-status" className="field !w-auto" value={selected} onChange={(e) => setNext(e.target.value)} disabled={busy || options.length === 0}>
          <option value="">Select status…</option>
          {options.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </select>
      </div>
      <button type="button" className="btn-primary" disabled={busy || selected === ""} onClick={() => { onChange(selected as InvestigationStatus); setNext(""); }}>
        {busy ? "Saving…" : "Update status"}
      </button>
    </div>
  );
}
