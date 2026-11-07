import { useState, type FormEvent } from "react";
import { addInvestigationNote } from "../../services/api";
import { MAX_NOTE_LENGTH, validateNote, type InvestigationDetail, type InvestigationNote } from "../../types/investigations";
import { formatTimestamp } from "../common/format";

interface Props {
  investigationId: string;
  notes: readonly InvestigationNote[];
  onAdded: (investigation: InvestigationDetail) => void;
}

/** Chronological timeline (oldest first) and an add-note form. Notes are append-only and plain text; the author is not recorded (no authentication yet). */
export default function NotesPanel({ investigationId, notes, onAdded }: Props) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaved(false);
    const problem = validateNote(text);
    setError(problem);
    if (problem) return;
    setSaving(true);
    try {
      onAdded(await addInvestigationNote(investigationId, text));
      setText("");
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the note.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      {notes.length === 0 ? (
        <p className="text-sm text-muted">No notes yet. Record findings as you investigate.</p>
      ) : (
        <ol className="space-y-3 border-l border-line-strong pl-4" aria-label="Notes, oldest first">
          {notes.map((note) => (
            <li key={note.note_id} className="relative">
              <span className="absolute -left-[1.4rem] top-1.5 h-2 w-2 rounded-full bg-neon" aria-hidden="true" />
              <p className="font-mono text-[11px] text-muted"><time dateTime={note.created_at}>{formatTimestamp(note.created_at)}</time></p>
              <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-fg">{note.text}</p>
            </li>
          ))}
        </ol>
      )}
      <form onSubmit={submit} aria-label="Add note" noValidate className="space-y-2">
        <label htmlFor="note-text" className="field-label">Add a note</label>
        <textarea id="note-text" className="field min-h-24" rows={4} value={text} maxLength={MAX_NOTE_LENGTH} onChange={(e) => { setText(e.target.value); setSaved(false); }} aria-describedby="note-help" />
        <p id="note-help" className="text-xs text-muted">{text.length} / {MAX_NOTE_LENGTH} characters. Plain text; notes cannot be edited later.</p>
        {error && <p className="text-sm text-critical" role="alert">{error}</p>}
        {saved && <p className="text-sm text-neon" role="status">Note added.</p>}
        <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Adding…" : "Add note"}</button>
      </form>
    </div>
  );
}
