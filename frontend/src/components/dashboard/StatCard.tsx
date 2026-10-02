interface StatCardProps {
  label: string;
  value: string;
  description: string;
  accentClass: string;
}

export default function StatCard({ label, value, description, accentClass }: StatCardProps) {
  return (
    <div className={`rounded-lg border border-slate-200 border-t-4 bg-white p-5 ${accentClass}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-slate-600">{label}</p>
        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-900">Sample data</span>
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums text-ink">{value}</p>
      <p className="mt-1 text-sm text-slate-500">{description}</p>
    </div>
  );
}
