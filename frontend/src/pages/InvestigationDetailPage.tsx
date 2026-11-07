import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import ErrorState from "../components/common/ErrorState";
import { formatTimestamp } from "../components/common/format";
import RefreshError from "../components/common/RefreshError";
import StateMessage from "../components/common/StateMessage";
import AlertPicker from "../components/investigations/AlertPicker";
import LinkedAlertsPanel from "../components/investigations/LinkedAlertsPanel";
import NotesPanel from "../components/investigations/NotesPanel";
import StatusControl from "../components/investigations/StatusControl";
import { useInvestigation } from "../hooks/useInvestigations";
import { useReportUpdated } from "../hooks/useRefresh";
import { linkAlerts, unlinkAlert, updateInvestigation } from "../services/api";
import { MAX_TITLE_LENGTH, validateTitle, type InvestigationDetail } from "../types/investigations";

type Feedback = { kind: "success" | "error"; text: string } | null;

export default function InvestigationDetailPage() {
  const { investigationId = "" } = useParams();
  const state = useInvestigation(investigationId);
  useReportUpdated(state.updatedAt);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [linking, setLinking] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  /** Runs one write, then refreshes the page data. Errors are shown, never thrown into the page. */
  async function run(action: () => Promise<InvestigationDetail>, success: string): Promise<boolean> {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      setFeedback({ kind: "success", text: success });
      state.reload();
      return true;
    } catch (err) {
      setFeedback({ kind: "error", text: err instanceof Error ? err.message : "The change could not be saved." });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveTitle(e: FormEvent) {
    e.preventDefault();
    const problem = validateTitle(titleDraft);
    if (problem) return setFeedback({ kind: "error", text: problem });
    if (await run(() => updateInvestigation(investigationId, { title: titleDraft.trim() }), "Title updated.")) setRenaming(false);
  }

  async function confirmLink() {
    if (await run(() => linkAlerts(investigationId, picked), `Linked ${picked.length} alert${picked.length === 1 ? "" : "s"}.`)) {
      setPicked([]);
      setLinking(false);
    }
  }

  if (state.kind === "loading") return <p className="text-sm text-muted" role="status">Loading investigation…</p>;
  if (state.kind === "error") {
    return (
      <div className="space-y-3">
        <Link to="/investigations" className="text-sm font-medium text-cyan hover:underline">← All investigations</Link>
        <ErrorState title="Could not load this investigation" message={state.message} onRetry={state.reload} />
      </div>
    );
  }

  const inv = state.data;
  return (
    <div className="space-y-6">
      <Link to="/investigations" className="text-sm font-medium text-cyan hover:underline">← All investigations</Link>
      <RefreshError errors={[state.refreshError]} updatedAt={state.updatedAt} onRetry={state.reload} />

      <section className="panel space-y-4 p-4" aria-label="Investigation summary">
        <div className="space-y-1">
          <p className="font-mono text-xs text-muted">{inv.investigation_id}</p>
          {renaming ? (
            <form onSubmit={saveTitle} className="flex flex-wrap items-end gap-2" aria-label="Rename investigation">
              <div className="min-w-[16rem] flex-1">
                <label htmlFor="inv-rename" className="field-label">Title</label>
                <input id="inv-rename" className="field" value={titleDraft} maxLength={MAX_TITLE_LENGTH} onChange={(e) => setTitleDraft(e.target.value)} autoComplete="off" />
              </div>
              <button type="submit" className="btn-primary" disabled={busy}>Save</button>
              <button type="button" className="btn" onClick={() => setRenaming(false)}>Cancel</button>
            </form>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="break-words text-lg font-semibold text-fg">{inv.title}</h2>
              <button type="button" className="btn" onClick={() => { setTitleDraft(inv.title); setRenaming(true); setFeedback(null); }}>Rename</button>
            </div>
          )}
          <p className="font-mono text-[11px] text-muted">Created {formatTimestamp(inv.created_at)} · Updated {formatTimestamp(inv.updated_at)}</p>
        </div>
        <StatusControl status={inv.status} busy={busy} onChange={(status) => void run(() => updateInvestigation(investigationId, { status }), "Investigation status updated.")} />
        <p className="text-xs text-muted">Changing the investigation status does not change the status, severity or priority of any linked alert.</p>
        {feedback && (
          <p className={`text-sm ${feedback.kind === "success" ? "text-neon" : "text-critical"}`} role={feedback.kind === "error" ? "alert" : "status"}>{feedback.text}</p>
        )}
      </section>

      <section aria-label="Linked alerts" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-fg">Linked alerts ({inv.alert_count})</h3>
          {!linking && <button type="button" className="btn" onClick={() => { setLinking(true); setFeedback(null); }}>Link alerts</button>}
        </div>
        {inv.unavailable_alert_count > 0 && (
          <StateMessage variant="empty" title={`${inv.unavailable_alert_count} linked alert${inv.unavailable_alert_count === 1 ? " is" : "s are"} no longer available.`}>
            Their details cannot be shown. You can unlink them.
          </StateMessage>
        )}
        {linking && (
          <div className="panel space-y-3 p-4">
            <AlertPicker linkedIds={inv.alert_ids} selected={picked} onChange={setPicked} idPrefix="link" />
            <div className="flex gap-2">
              <button type="button" className="btn-primary" disabled={busy || picked.length === 0} onClick={() => void confirmLink()}>
                {busy ? "Linking…" : `Link ${picked.length || ""} selected`.trim()}
              </button>
              <button type="button" className="btn" disabled={busy} onClick={() => { setLinking(false); setPicked([]); }}>Cancel</button>
            </div>
          </div>
        )}
        <LinkedAlertsPanel alerts={inv.alerts} busy={busy} onUnlink={(alertId) => void run(() => unlinkAlert(investigationId, alertId), `Unlinked ${alertId}.`)} />
      </section>

      <section aria-label="Notes" className="space-y-3">
        <h3 className="text-sm font-semibold text-fg">Notes ({inv.note_count})</h3>
        <NotesPanel investigationId={investigationId} notes={inv.notes} onAdded={() => state.reload()} />
      </section>
    </div>
  );
}
