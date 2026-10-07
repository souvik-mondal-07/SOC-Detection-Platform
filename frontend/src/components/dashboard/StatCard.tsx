interface StatCardProps {
  label: string;
  value: string;
  description: string;
  accentClass: string;
  /** Dimmed styling for figures the backend cannot provide yet. */
  unavailable?: boolean;
}

export default function StatCard({ label, value, description, accentClass, unavailable = false }: StatCardProps) {
  return (
    <div className={`rounded-lg border border-slate-200 border-t-4 bg-white p-5 ${accentClass}`}>
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${unavailable ? "text-slate-400" : "text-ink"}`}>{value}</p>
      <p className="mt-1 text-sm text-slate-500">{description}</p>
    </div>
  );
}
