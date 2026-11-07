import { useState, type FormEvent } from "react";
import { createInvestigation } from "../../services/api";
import { MAX_TITLE_LENGTH, validateTitle, type InvestigationDetail } from "../../types/investigations";
import AlertPicker from "./AlertPicker";

interface Props {
  onCreated: (investigation: InvestigationDetail) => void;
  onCancel: () => void;
}

export default function CreateInvestigationForm({ onCreated, onCancel }: Props) {
  const [title, setTitle] = useState("");
  const [alertIds, setAlertIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const problem = validateTitle(title) ?? (alertIds.length === 0 ? "Select at least one alert to investigate." : null);
    setError(problem);
    if (problem) return;
    setSubmitting(true);
    try {
      onCreated(await createInvestigation(title, alertIds));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the investigation.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="panel space-y-4 p-4" aria-label="Create investigation" noValidate>
      <div>
        <label htmlFor="inv-title" className="field-label">Title</label>
        <input id="inv-title" className="field" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={MAX_TITLE_LENGTH} autoComplete="off" placeholder="e.g. Brute-force attempts from 192.168.1.20" aria-describedby={error ? "inv-form-error" : undefined} />
      </div>
      <fieldset>
        <legend className="field-label">Alerts to investigate</legend>
        <div className="mt-2">
          <AlertPicker selected={alertIds} onChange={setAlertIds} idPrefix="create" />
        </div>
      </fieldset>
      {error && <p id="inv-form-error" className="text-sm text-critical" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={submitting}>{submitting ? "Creating…" : "Create investigation"}</button>
        <button type="button" className="btn" onClick={onCancel} disabled={submitting}>Cancel</button>
      </div>
    </form>
  );
}
