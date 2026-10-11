import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  /** Says exactly which data the chart is built from (e.g. "newest 500 events"). */
  note?: string;
  children: ReactNode;
}

export default function ChartCard({ title, note, children }: ChartCardProps) {
  return (
    <section className="panel min-w-0 p-5 transition-colors hover:border-line-strong" aria-label={title}>
      <h2 className="flex items-center gap-2 font-mono text-[13px] font-bold uppercase tracking-[0.12em] text-fg">
        <span className="h-3 w-1 rounded-sm bg-neon" aria-hidden="true" />
        {title}
      </h2>
      {note && <p className="mt-1 text-xs leading-snug text-muted">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}
