import { SEVERITY_DOT } from "../common/StatusBadge";
import { ALERT_SEVERITIES } from "../../types/alerts";

const LABEL_TONE: Record<string, string> = { critical: "text-critical", high: "text-high", medium: "text-medium", low: "text-low" };

/** One bar showing how all stored alerts split by severity. Uses only the exact per-severity counts from the alerts API. */
export default function ThreatPosture({ bySeverity, total }: { bySeverity: Record<string, number>; total: number }) {
  const summary = ALERT_SEVERITIES.map((s) => `${s} ${bySeverity[s] ?? 0}`).join(", ");
  return (
    <section className="panel p-5" aria-label="Threat posture">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="flex items-center gap-2 font-mono text-[13px] font-bold uppercase tracking-[0.12em] text-fg">
          <span className="h-3 w-1 rounded-sm bg-neon" aria-hidden="true" />
          Threat posture
        </h2>
        <p className="text-xs text-muted">All stored alerts by severity</p>
      </div>
      {total === 0 ? (
        <p className="mt-4 rounded border border-dashed border-line-strong p-4 text-center text-sm text-muted" role="status">
          No alerts recorded. Alerts appear after detection runs on ingested events.
        </p>
      ) : (
        <>
          <div className="mt-4 flex h-3 overflow-hidden rounded bg-line" role="img" aria-label={`Alerts by severity: ${summary}`}>
            {[...ALERT_SEVERITIES].reverse().map((s) => {
              const count = bySeverity[s] ?? 0;
              return count > 0 ? <div key={s} className={SEVERITY_DOT[s]} style={{ width: `${(count / total) * 100}%` }} title={`${s}: ${count}`} /> : null;
            })}
          </div>
          <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[...ALERT_SEVERITIES].reverse().map((s) => (
              <li key={s} className="flex items-baseline gap-2">
                <span className={`h-2 w-2 shrink-0 rounded-full ${SEVERITY_DOT[s]}`} aria-hidden="true" />
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted">{s}</span>
                <span className={`font-mono text-lg font-bold tabular-nums ${LABEL_TONE[s]}`}>{bySeverity[s] ?? 0}</span>
                <span className="font-mono text-xs text-dim">{total > 0 ? `${Math.round(((bySeverity[s] ?? 0) / total) * 100)}%` : ""}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
