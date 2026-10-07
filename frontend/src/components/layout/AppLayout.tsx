import { useState } from "react";
import { Outlet, useLocation, useOutletContext } from "react-router-dom";
import { NAV_ITEMS } from "../../config/navigation";
import { useBackendHealth, type BackendState } from "../../hooks/useBackendHealth";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export interface LayoutContext {
  backend: BackendState;
}

/** Pages read the shared backend health through this hook. */
export function useLayoutContext(): LayoutContext {
  return useOutletContext<LayoutContext>();
}

export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const backend = useBackendHealth();
  const { pathname } = useLocation();
  const title = NAV_ITEMS.find((item) => item.path === pathname)?.label ?? "Not found";

  return (
    <div className="min-h-screen">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="lg:pl-64">
        <TopBar title={title} backend={backend} onMenuClick={() => setMenuOpen(true)} />
        <main className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
          <Outlet context={{ backend } satisfies LayoutContext} />
        </main>
      </div>
    </div>
  );
}
