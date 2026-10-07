// One place that decides how statuses and severities look. Unknown values (backend data is untrusted) are shown neutral.
const TONES: Record<string, string> = {
  success: "bg-emerald-50 text-resolved ring-emerald-200",
  failed: "bg-red-50 text-critical ring-red-200",
  blocked: "bg-amber-50 text-warning ring-amber-200",
  unknown: "bg-slate-100 text-slate-600 ring-slate-200",
  // Severities, for the rules and alerts pages once the backend exposes them.
  low: "bg-sky-50 text-sky-800 ring-sky-200",
  medium: "bg-amber-50 text-warning ring-amber-200",
  high: "bg-orange-50 text-orange-800 ring-orange-200",
  critical: "bg-red-50 text-critical ring-red-200",
};
const NEUTRAL = "bg-slate-100 text-slate-700 ring-slate-200";

export default function StatusBadge({ value }: { value: string }) {
  const tone = Object.hasOwn(TONES, value) ? TONES[value] : NEUTRAL;
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${tone}`}>{value}</span>;
}
