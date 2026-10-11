import type { ReactNode } from "react";

/** Term/value rows for detail panels. */
export default function DetailList({ rows }: { rows: readonly (readonly [string, ReactNode])[] }) {
  return (
    <dl className="space-y-3 text-sm">
      {rows.map(([term, detail]) => (
        <div key={term} className="grid grid-cols-[8rem_1fr] gap-2 border-b border-line/60 pb-2">
          <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">{term}</dt>
          <dd className="min-w-0 break-words text-fg">{detail}</dd>
        </div>
      ))}
    </dl>
  );
}
