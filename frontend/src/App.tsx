import { useState } from "react";
import BackendStatusPanel from "./components/dashboard/BackendStatusPanel";
import StatCard from "./components/dashboard/StatCard";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import type { NavItem } from "./config/navigation";
import { useBackendHealth } from "./hooks/useBackendHealth";

// Placeholder values only. These are NOT real security telemetry.
const SAMPLE_STATS = [
  { label: "Total events", value: "12,480", description: "All ingested events", accentClass: "border-t-accent" },
  { label: "Active alerts", value: "37", description: "Awaiting triage", accentClass: "border-t-warning" },
  { label: "Critical alerts", value: "5", description: "Highest severity", accentClass: "border-t-critical" },
  { label: "Resolved alerts", value: "212", description: "Closed after review", accentClass: "border-t-resolved" },
];

export default function App() {
  const [active, setActive] = useState<NavItem>("Overview");
  const [menuOpen, setMenuOpen] = useState(false);
  const backend = useBackendHealth();

  return (
    <div className="min-h-screen">
      <Sidebar active={active} onSelect={setActive} open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="lg:pl-64">
        <TopBar title={active} backend={backend} onMenuClick={() => setMenuOpen(true)} />
        <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
          <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="note">
            All figures on this page are sample placeholders, not real security telemetry. Event collection and
            detection are not built yet.
          </div>

          {active === "Overview" ? (
            <>
              <section aria-label="Summary figures" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {SAMPLE_STATS.map((stat) => (
                  <StatCard key={stat.label} {...stat} />
                ))}
              </section>
              <BackendStatusPanel backend={backend} />
            </>
          ) : (
            <section className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
              <h2 className="text-base font-semibold text-ink">{active}</h2>
              <p className="mt-1 text-sm text-slate-500">This section is a placeholder and will be built in a later step.</p>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
