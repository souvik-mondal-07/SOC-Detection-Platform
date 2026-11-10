import { useRef, useState } from "react";
import { acknowledgeAlert, changeAlertStatus } from "../../services/api";
import { STATUS_REASON_MAX, availableActions, canAcknowledge, validateReason, type AlertDetail, type TransitionAction } from "../../types/alerts";
import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";

interface Props {
  alert: AlertDetail;
  /** Called only after the backend has confirmed the change, with the alert as the backend now has it. */
  onChanged: (updated: AlertDetail, message: string) => void;
}

/**
 * Current status plus the transitions the backend allows from it. The backend validates everything again.
 * Resolve, false positive and reopen ask for a reason and an explicit confirmation. Success is only shown after the API replies.
 */
export default function AlertLifecyclePanel({ alert, onChanged }: Props) {
  const [pending, setPending] = useState<TransitionAction | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const inFlight = useRef(false); // blocks a second submit in the same tick, before `busy` has re-rendered

  async function run(label: string, call: () => Promise<AlertDetail>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await call();
      setPending(null);
      setReason("");
      setMessage(label);
      onChanged(updated, label);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The change could not be saved.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function choose(action: TransitionAction) {
    setError(null);
    setMessage(null);
    if (action.needsReason) {
      setPending(action);
      setReason("");
    } else {
      void run(`Alert is now ${action.to.replace(/_/g, " ")}.`, () => changeAlertStatus(alert.alert_id, action.to));
    }
  }

  function confirm() {
    if (!pending) return;
    const problem = validateReason(reason, pending.needsReason);
    if (problem) {
      setError(problem);
      return;
    }
    const action = pending;
    void run(`Alert is now ${action.to.replace(/_/g, " ")}.`, () => changeAlertStatus(alert.alert_id, action.to, reason));
  }

  const actions = availableActions(alert.status);
  const textId = `reason-${alert.alert_id}`;

  return (
    <section aria-label="Alert lifecycle" className="space-y-3 rounded border border-line bg-panel-2/40 p-3">
      <div className="flex flex-wrap items-center gap-3">
        <h4 className="text-sm font-semibold text-fg">Status</h4>
        <StatusBadge value={alert.status} />
        {alert.acknowledged_at && alert.status === "open" && <span className="font-mono text-[11px] text-muted">Acknowledged {formatTimestamp(alert.acknowledged_at)}</span>}
      </div>

      {alert.resolution_note && (alert.status === "resolved" || alert.status === "false_positive") && (
        <p className="whitespace-pre-wrap break-words text-sm text-body">
          <span className="field-label">{alert.status === "resolved" ? "Resolution note" : "False-positive reason"}</span>
          {alert.resolution_note}
        </p>
      )}

      {!pending && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Status actions">
          {canAcknowledge(alert) && (
            <button type="button" className="btn" disabled={busy} onClick={() => void run("Alert acknowledged.", () => acknowledgeAlert(alert.alert_id))}>
              Acknowledge
            </button>
          )}
          {actions.map((action) => (
            <button key={action.to} type="button" className={action.tone === "primary" ? "btn-primary disabled:opacity-45" : "btn"} disabled={busy} onClick={() => choose(action)}>
              {action.label}
            </button>
          ))}
          {actions.length === 0 && <p className="text-sm text-muted">No status changes are available for “{alert.status}”.</p>}
        </div>
      )}

      {pending && (
        <form
          role="group"
          aria-label={`Confirm: ${pending.label}`}
          className="space-y-2"
          onSubmit={(e) => { e.preventDefault(); confirm(); }}
        >
          <p className="text-sm text-fg">
            {pending.label === "Reopen" ? "Reopen this alert?" : pending.to === "resolved" ? "Resolve this alert?" : "Mark this alert as a false positive?"}{" "}
            <span className="text-muted">The change is recorded in the status history.</span>
          </p>
          <div>
            <label htmlFor={textId} className="field-label">{pending.reasonLabel}</label>
            <textarea
              id={textId} className="field" rows={3} value={reason} maxLength={STATUS_REASON_MAX} disabled={busy} autoFocus
              onChange={(e) => setReason(e.target.value)} aria-required={pending.needsReason}
            />
            <p className="mt-0.5 text-right font-mono text-[11px] text-muted">{reason.length} / {STATUS_REASON_MAX}</p>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary disabled:opacity-45" disabled={busy}>{busy ? "Saving…" : `Confirm: ${pending.label}`}</button>
            <button type="button" className="btn" disabled={busy} onClick={() => { setPending(null); setError(null); }}>Cancel</button>
          </div>
        </form>
      )}

      {error && <p className="text-sm text-critical" role="alert">{error}</p>}
      {message && !error && <p className="text-sm text-neon" role="status">{message}</p>}
    </section>
  );
}
