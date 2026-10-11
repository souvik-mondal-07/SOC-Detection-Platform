import type { NavItem } from "../../config/navigation";
import type { BackendState } from "../../hooks/useBackendHealth";
import { formatClock } from "../common/format";
import Icon from "../common/Icons";
import Clock from "./Clock";

export const REFRESH_OPTIONS = [
  { label: "Off", seconds: 0 },
  { label: "30 s", seconds: 30 },
  { label: "1 min", seconds: 60 },
  { label: "5 min", seconds: 300 },
] as const;

interface TopBarProps {
  page: Pick<NavItem, "title" | "subtitle">;
  backend: BackendState;
  onMenuClick: () => void;
  onRefresh: () => void;
  intervalSeconds: number;
  onIntervalChange: (seconds: number) => void;
  lastUpdated: Date | null;
}

function statusLabel(backend: BackendState): { text: string; dot: string } {
  if (backend.kind === "loading") return { text: "Checking backend…", dot: "bg-dim" };
  if (backend.kind === "offline") return { text: "Backend offline", dot: "bg-critical" };
  return backend.data.database === "connected"
    ? { text: "Backend online · database connected", dot: "bg-neon shadow-[0_0_6px_var(--color-neon)]" }
    : { text: "Backend online · database unavailable", dot: "bg-medium" };
}

export default function TopBar({ page, backend, onMenuClick, onRefresh, intervalSeconds, onIntervalChange, lastUpdated }: TopBarProps) {
  const status = statusLabel(backend);
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-void/85 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="rounded-md border border-line-strong p-2 text-muted hover:text-fg lg:hidden"
          aria-label="Open navigation menu"
        >
          <Icon name="menu" className="h-5 w-5" />
        </button>

        <div className="min-w-0">
          <h1 className="font-mono text-lg font-bold tracking-[0.12em] text-fg sm:text-xl">{page.title}</h1>
          <p className="text-xs text-muted">{page.subtitle}</p>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-2 text-xs" role="status">
            <span className={`h-2 w-2 rounded-full ${status.dot}`} aria-hidden="true" />
            <span className="text-body">{status.text}</span>
          </div>
          <div className="flex items-center gap-2" title="Current local time">
            <Icon name="clock" className="h-4 w-4 text-dim" />
            <Clock />
          </div>
          <p className="font-mono text-xs text-muted" role="status">
            {lastUpdated ? `Updated ${formatClock(lastUpdated)}` : "Not loaded yet"}
          </p>
          <label className="flex items-center gap-2 text-xs text-muted">
            <span className="font-mono uppercase tracking-wider">Auto</span>
            <select
              value={intervalSeconds}
              onChange={(e) => onIntervalChange(Number(e.target.value))}
              aria-label="Auto-refresh interval"
              className="rounded-md border border-line-strong px-2 py-1 text-xs"
            >
              {REFRESH_OPTIONS.map((o) => (
                <option key={o.seconds} value={o.seconds}>{o.label}</option>
              ))}
            </select>
          </label>
          <button type="button" onClick={onRefresh} className="btn-primary gap-2">
            <Icon name="refresh" className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>
    </header>
  );
}
