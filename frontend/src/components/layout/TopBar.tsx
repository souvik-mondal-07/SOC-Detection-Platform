import type { BackendState } from "../../hooks/useBackendHealth";

interface TopBarProps {
  title: string;
  backend: BackendState;
  onMenuClick: () => void;
}

const STATUS_LABEL: Record<BackendState["kind"], string> = {
  loading: "Checking backend…",
  online: "Backend online",
  offline: "Backend offline",
};

const STATUS_DOT: Record<BackendState["kind"], string> = {
  loading: "bg-slate-400",
  online: "bg-resolved",
  offline: "bg-critical",
};

export default function TopBar({ title, backend, onMenuClick }: TopBarProps) {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-md p-2 text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-accent lg:hidden"
        aria-label="Open navigation menu"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
        </svg>
      </button>
      <h1 className="text-lg font-semibold text-ink">{title}</h1>
      <div className="ml-auto flex items-center gap-2 text-sm text-slate-600" role="status">
        <span className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[backend.kind]}`} aria-hidden="true" />
        {STATUS_LABEL[backend.kind]}
      </div>
    </header>
  );
}
