import { SEVERITY_DOT } from "./StatusBadge";

/** Priority 0-100 as a number with a small meter. The meter colour follows the alert's severity. */
export default function PriorityScore({ score, severity }: { score: number; severity: string }) {
  const width = Math.max(0, Math.min(100, score));
  const colour = Object.hasOwn(SEVERITY_DOT, severity) ? SEVERITY_DOT[severity] : "bg-muted";
  return (
    <div className="flex items-center gap-2" title={`Priority ${score} of 100`}>
      <span className="w-7 text-right font-mono text-base font-bold tabular-nums text-fg">{score}</span>
      <span className="h-1 w-12 overflow-hidden rounded bg-line" aria-hidden="true">
        <span className={`block h-full ${colour}`} style={{ width: `${width}%` }} />
      </span>
    </div>
  );
}
