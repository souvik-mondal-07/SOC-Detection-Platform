import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { NAV_ITEMS } from "../../config/navigation";
import { useBackendHealth } from "../../hooks/useBackendHealth";
import type { LayoutContext } from "../../hooks/useRefresh";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

const DEFAULT_INTERVAL_SECONDS = 60;

export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [intervalSeconds, setIntervalSeconds] = useState(DEFAULT_INTERVAL_SECONDS);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const backend = useBackendHealth(refreshKey);
  const { pathname } = useLocation();
  const page = NAV_ITEMS.find((item) => pathname === item.path || pathname.startsWith(`${item.path}/`)) ?? { title: "PAGE NOT FOUND", subtitle: "This address does not match a page" };

  const refresh = useCallback(() => setRefreshKey((n) => n + 1), []);

  // Each tick bumps the shared refresh key; every data hook aborts its previous request first, so requests never pile up.
  useEffect(() => {
    if (intervalSeconds <= 0) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) refresh();
    }, intervalSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [intervalSeconds, refresh]);

  const context: LayoutContext = { backend, refreshKey, refresh, reportUpdated: setLastUpdated };

  return (
    <div className="min-h-screen">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} backend={backend} />
      <div className="lg:pl-64">
        <TopBar
          page={page}
          backend={backend}
          onMenuClick={() => setMenuOpen(true)}
          onRefresh={refresh}
          intervalSeconds={intervalSeconds}
          onIntervalChange={setIntervalSeconds}
          lastUpdated={lastUpdated}
        />
        <main className="mx-auto max-w-[96rem] space-y-6 p-4 sm:p-6">
          <Outlet context={context} />
        </main>
      </div>
    </div>
  );
}
