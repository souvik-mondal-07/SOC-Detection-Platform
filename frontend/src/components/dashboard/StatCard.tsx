import Icon, { type IconName } from "../common/Icons";
import { Skeleton } from "../common/Skeleton";

export type Tone = "neon" | "cyan" | "critical" | "high" | "medium" | "muted";

const TONES: Record<Tone, { text: string; border: string; icon: string; glow: string }> = {
  neon: { text: "text-neon", border: "border-t-neon", icon: "border-neon/40 bg-neon/10 text-neon", glow: "hover:shadow-[0_0_24px_rgb(57_255_136/0.12)]" },
  cyan: { text: "text-cyan", border: "border-t-cyan", icon: "border-cyan/40 bg-cyan/10 text-cyan", glow: "hover:shadow-[0_0_24px_rgb(34_211_238/0.12)]" },
  critical: { text: "text-critical", border: "border-t-critical", icon: "border-critical/40 bg-critical/10 text-critical", glow: "hover:shadow-[0_0_24px_rgb(242_85_90/0.14)]" },
  high: { text: "text-high", border: "border-t-high", icon: "border-high/40 bg-high/10 text-high", glow: "hover:shadow-[0_0_24px_rgb(249_115_22/0.12)]" },
  medium: { text: "text-medium", border: "border-t-medium", icon: "border-medium/40 bg-medium/10 text-medium", glow: "hover:shadow-[0_0_24px_rgb(245_165_36/0.12)]" },
  muted: { text: "text-fg", border: "border-t-line-strong", icon: "border-line-strong bg-panel-2 text-muted", glow: "" },
};

interface StatCardProps {
  label: string;
  value: string;
  description: string;
  icon: IconName;
  tone: Tone;
  loading?: boolean;
  /** Dimmed styling when the figure cannot be provided (error). */
  unavailable?: boolean;
}

export default function StatCard({ label, value, description, icon, tone, loading = false, unavailable = false }: StatCardProps) {
  const t = TONES[unavailable || loading ? "muted" : tone];
  return (
    <div className={`panel border-t-2 p-5 transition duration-200 hover:-translate-y-0.5 ${t.border} ${t.glow}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md border ${t.icon}`}>
          <Icon name={icon} className="h-[18px] w-[18px]" />
        </span>
      </div>
      {loading ? (
        <div role="status" aria-label={`Loading ${label}`}><Skeleton className="mt-3 h-9 w-24" /></div>
      ) : (
        <p className={`mt-3 font-mono font-bold tabular-nums ${unavailable ? "text-xl text-dim" : `text-4xl ${t.text}`}`}>{value}</p>
      )}
      <p className={`mt-2 text-xs leading-snug ${unavailable ? "text-critical" : "text-muted"}`}>{description}</p>
    </div>
  );
}
