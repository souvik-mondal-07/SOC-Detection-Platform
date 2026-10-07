import BackendStatusPanel from "../components/dashboard/BackendStatusPanel";
import RecentEventsPanel from "../components/dashboard/RecentEventsPanel";
import StatCard from "../components/dashboard/StatCard";
import { useLayoutContext } from "../components/layout/AppLayout";

export default function DashboardPage() {
  const { backend } = useLayoutContext();

  const backendValue = backend.kind === "online" ? "Online" : backend.kind === "offline" ? "Offline" : "Checking…";
  const backendAccent = backend.kind === "online" ? "border-t-resolved" : backend.kind === "offline" ? "border-t-critical" : "border-t-slate-300";
  const database = backend.kind === "online" ? backend.data.database : null;

  return (
    <>
      <section aria-label="Summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Backend" value={backendValue} description="From the health endpoint" accentClass={backendAccent} />
        <StatCard
          label="Database"
          value={database ? (database === "connected" ? "Connected" : "Unavailable") : "—"}
          description={database ? "MongoDB connection" : "Known once the backend answers"}
          accentClass={database === "connected" ? "border-t-resolved" : database ? "border-t-critical" : "border-t-slate-300"}
          unavailable={!database}
        />
        <StatCard label="Alerts" value="Not available yet" description="Backend endpoint not available yet" accentClass="border-t-slate-300" unavailable />
        <StatCard label="Detection rules" value="Not available yet" description="Backend endpoint not available yet" accentClass="border-t-slate-300" unavailable />
      </section>
      <RecentEventsPanel />
      <BackendStatusPanel backend={backend} />
    </>
  );
}
