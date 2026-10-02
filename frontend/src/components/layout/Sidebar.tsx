import { NAV_ITEMS, type NavItem } from "../../config/navigation";

interface SidebarProps {
  active: NavItem;
  onSelect: (item: NavItem) => void;
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ active, onSelect, open, onClose }: SidebarProps) {
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
        <nav className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                onSelect(item);
                onClose();
              }}
              aria-current={item === active ? "page" : undefined}
              className={`w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                item === active
                  ? "bg-ink-soft text-white shadow-[inset_3px_0_0_var(--color-accent)]"
                  : "hover:bg-ink-soft/60 hover:text-white"
              }`}
            >
              {item}
            </button>
          ))}
        </nav>
        <p className="border-t border-white/10 px-6 py-4 text-xs text-slate-500">Step 1 foundation build</p>
      </aside>
    </>
  );
}
