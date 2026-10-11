// One place that decides how statuses and severities look. Unknown values (backend data is untrusted) are shown neutral.
const SEVERITY: Record<string, string> = {
  critical: "bg-critical/15 text-critical ring-critical/50",
  high: "bg-high/15 text-high ring-high/45",
  medium: "bg-medium/15 text-medium ring-medium/40",
  low: "bg-low/15 text-low ring-low/40",
};
const OTHER: Record<string, string> = {
  // Event outcomes
  success: "bg-neon/10 text-neon ring-neon/35",
  failed: "bg-critical/15 text-critical ring-critical/45",
  blocked: "bg-medium/15 text-medium ring-medium/40",
  unknown: "bg-panel-2 text-muted ring-line-strong",
  // Alert statuses
  open: "bg-cyan/10 text-cyan ring-cyan/40",
  investigating: "bg-indigo-400/10 text-indigo-300 ring-indigo-400/40",
  resolved: "bg-neon/10 text-neon ring-neon/35",
  false_positive: "bg-panel-2 text-muted ring-line-strong",
  // Rule state
  enabled: "bg-neon/10 text-neon ring-neon/35",
  disabled: "bg-panel-2 text-muted ring-line-strong",
};
const NEUTRAL = "bg-panel-2 text-body ring-line-strong";

export const SEVERITY_DOT: Record<string, string> = { critical: "bg-critical", high: "bg-high", medium: "bg-medium", low: "bg-low" };

/** Left edge marker for table rows, by severity. */
export const SEVERITY_EDGE: Record<string, string> = {
  critical: "shadow-[inset_3px_0_0_var(--color-critical)]",
  high: "shadow-[inset_3px_0_0_var(--color-high)]",
  medium: "shadow-[inset_3px_0_0_var(--color-medium)]",
  low: "shadow-[inset_3px_0_0_var(--color-low)]",
};

export default function StatusBadge({ value }: { value: string }) {
  const isSeverity = Object.hasOwn(SEVERITY, value);
  const tone = isSeverity ? SEVERITY[value] : Object.hasOwn(OTHER, value) ? OTHER[value] : NEUTRAL;
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider ring-1 ring-inset ${tone}`}>
      {isSeverity && <span className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[value]}`} aria-hidden="true" />}
      {value.replace(/_/g, " ")}
    </span>
  );
}
