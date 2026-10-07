import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../config/navigation";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {open && (
        <div className="fixed inset-0 z-20 bg-black/40 lg:hidden" onClick={onClose} aria-hidden="true" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 flex-col bg-ink text-slate-300 transition-transform lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Primary"
      >
        <div className="border-b border-white/10 px-6 py-5">
          <p className="text-lg font-semibold text-white">SOC Detection</p>
          <p className="text-sm text-slate-400">Monitoring platform</p>
        </div>
        <nav className="flex-1 space-y-1 p-3" aria-label="Sections">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              className={({ isActive }) =>
                `block w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                  isActive
                    ? "bg-ink-soft text-white shadow-[inset_3px_0_0_var(--color-accent)]"
                    : "hover:bg-ink-soft/60 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <p className="border-t border-white/10 px-6 py-4 text-xs text-slate-500">Version {__APP_VERSION__}</p>
      </aside>
    </>
  );
}
