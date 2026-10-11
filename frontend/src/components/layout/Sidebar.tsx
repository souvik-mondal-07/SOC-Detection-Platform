import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../config/navigation";
import type { BackendState } from "../../hooks/useBackendHealth";
import Icon from "../common/Icons";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  backend: BackendState;
}

function health(backend: BackendState): { label: string; dot: string; text: string } {
  if (backend.kind === "loading") return { label: "Checking…", dot: "bg-dim", text: "text-muted" };
  if (backend.kind === "offline") return { label: "Offline", dot: "bg-critical", text: "text-critical" };
  return backend.data.database === "connected"
    ? { label: "Online", dot: "bg-neon shadow-[0_0_6px_var(--color-neon)]", text: "text-neon" }
    : { label: "Degraded", dot: "bg-medium", text: "text-medium" };
}

export default function Sidebar({ open, onClose, backend }: SidebarProps) {
  // Escape closes the mobile menu.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const status = health(backend);
  const database = backend.kind === "online" ? backend.data.database : null;

  return (
    <>
      {open && <div className="fixed inset-0 z-20 bg-black/70 lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-line bg-void/95 backdrop-blur transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Primary"
      >
        <div className="flex items-center gap-3 border-b border-line px-5 py-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-neon/50 bg-neon/10 text-neon shadow-[0_0_14px_rgb(57_255_136/0.18)]">
            <Icon name="shield" className="h-6 w-6" />
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[13px] font-bold leading-tight tracking-[0.14em] text-fg">SOC COMMAND</p>
            <p className="font-mono text-[13px] font-bold leading-tight tracking-[0.14em] text-neon">CENTER</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Sections">
          {NAV_ITEMS.map((item) =>
            item.planned ? (
              <div
                key={item.path}
                aria-disabled="true"
                className="flex w-full cursor-not-allowed items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-dim"
                title="Planned for a later roadmap step"
              >
                <Icon name={item.icon} className="h-[18px] w-[18px]" />
                <span className="flex-1">{item.label}</span>
                <span className="rounded border border-line-strong px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-dim">Planned</span>
              </div>
            ) : (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `group flex w-full items-center gap-3 rounded-md border px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "border-neon/40 bg-neon/10 text-neon shadow-[inset_3px_0_0_var(--color-neon)]"
                      : "border-transparent text-muted hover:border-line-strong hover:bg-panel-2 hover:text-fg"
                  }`
                }
              >
                <Icon name={item.icon} className="h-[18px] w-[18px]" />
                {item.label}
              </NavLink>
            ),
          )}
        </nav>

        <div className="space-y-2 border-t border-line px-5 py-4" role="status" aria-label="Backend health">
          <p className="tech-label">System</p>
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-body"><Icon name="server" className="h-4 w-4 text-muted" />Backend</span>
            <span className={`flex items-center gap-2 font-mono font-semibold uppercase ${status.text}`}>
              <span className={`h-2 w-2 rounded-full ${status.dot}`} aria-hidden="true" />
              {status.label}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-body"><Icon name="database" className="h-4 w-4 text-muted" />Database</span>
            <span className={`font-mono font-semibold uppercase ${database === "connected" ? "text-neon" : database ? "text-medium" : "text-muted"}`}>
              {database ?? "—"}
            </span>
          </div>
          <p className="pt-1 font-mono text-[10px] tracking-wider text-dim">v{__APP_VERSION__} · MONITOR. DETECT. INVESTIGATE. DEFEND.</p>
        </div>
      </aside>
    </>
  );
}
