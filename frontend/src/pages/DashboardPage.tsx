import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AlertDetails from "../components/alerts/AlertDetails";
import AlertFeed from "../components/dashboard/AlertFeed";
import ThreatPosture from "../components/dashboard/ThreatPosture";
import ChartCard from "../components/charts/ChartCard";
import CountBarChart, { SEVERITY_COLORS, STATUS_COLORS } from "../components/charts/CountBarChart";
import TrendChart from "../components/charts/TrendChart";
import RefreshError from "../components/common/RefreshError";
import StateMessage from "../components/common/StateMessage";
import BackendStatusPanel from "../components/dashboard/BackendStatusPanel";
import RecentEventsPanel from "../components/dashboard/RecentEventsPanel";
import SectionState from "../components/dashboard/SectionState";
import StatCard from "../components/dashboard/StatCard";
import { type AlertCounts, useAlertCounts, useAlertSample, useEventSample, useRuleCounts, EVENT_SAMPLE_LIMIT, MAX_ALERT_SAMPLE_PAGES } from "../hooks/useDashboard";
import { useLayoutContext, useReportUpdated } from "../hooks/useRefresh";
import { bucketByTime, countBy } from "../lib/aggregate";
import { ALERT_SEVERITIES, ALERT_STATUSES } from "../types/alerts";


export default function DashboardPage() {
  const { backend, refresh } = useLayoutContext();
  const counts = useAlertCounts();
  const sample = useAlertSample();
  const events = useEventSample();
  const rules = useRuleCounts();
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null);

  // "Last updated" is the oldest successful retrieval among the sections, shown only once all of them have loaded.
  const times = [counts.updatedAt, sample.updatedAt, events.updatedAt, rules.updatedAt];
  useReportUpdated(times.every((t) => t !== null) ? new Date(Math.min(...times.map((t) => t!.getTime()))) : null);

  const severityData = useMemo(
    () => (counts.kind === "loaded" ? ALERT_SEVERITIES.map((name) => ({ name, value: counts.data.bySeverity[name] ?? 0 })) : []),
    [counts],
  );
  const statusData = useMemo(
    () => (counts.kind === "loaded" ? ALERT_STATUSES.map((name) => ({ name, value: counts.data.byStatus[name] ?? 0 })) : []),
    [counts],
  );

  const alertValue = (pick: (c: AlertCounts) => number): string =>
    counts.kind === "loaded" ? String(pick(counts.data)) : counts.kind === "loading" ? "…" : "Unavailable";
  const alertDescription = (text: string) => (counts.kind === "error" ? counts.message : text);

  const eventsValue = events.kind === "loaded" ? (events.data.complete ? String(events.data.events.length) : `${EVENT_SAMPLE_LIMIT}+`) : events.kind === "loading" ? "…" : "Unavailable";
  const eventsDescription =
    events.kind === "error" ? events.message
    : events.kind === "loaded" && !events.data.complete ? `Newest ${EVENT_SAMPLE_LIMIT} loaded; the API has no total count`
    : "All stored events";

  const rulesValue = rules.kind === "loaded" ? String(rules.data.total) : rules.kind === "loading" ? "…" : "Unavailable";

  const eventTypeData = useMemo(() => (events.kind === "loaded" ? countBy(events.data.events, (e) => e.event_type) : []), [events]);
  const eventSourceData = useMemo(() => (events.kind === "loaded" ? countBy(events.data.events, (e) => e.source) : []), [events]);
  const trend = useMemo(() => (sample.kind === "loaded" ? bucketByTime(sample.data.alerts.map((a) => a.created_at)) : null), [sample]);

  const sampled = sample.kind === "loaded" && sample.data.alerts.length < sample.data.total;
  const eventsNote = events.kind === "loaded" ? (events.data.complete ? `All ${events.data.events.length} stored events` : `Newest ${EVENT_SAMPLE_LIMIT} events (the API cannot count or page beyond this)`) : undefined;

  const refreshErrors = [counts.refreshError, sample.refreshError, events.refreshError, rules.refreshError];
  const oldest = times.every((t) => t !== null) ? new Date(Math.min(...times.map((t) => t!.getTime()))) : null;

  return (
    <>
      <RefreshError errors={refreshErrors} updatedAt={oldest} onRetry={refresh} />
      <SectionState state={counts} reload={counts.reload} title="threat posture">
        {(data) => <ThreatPosture bySeverity={data.bySeverity} total={data.total} />}
      </SectionState>

      <section aria-label="Key metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total alerts" icon="alert" tone="cyan"
          value={alertValue((c) => c.total)} description={alertDescription("All stored alerts")}
          loading={counts.kind === "loading"} unavailable={counts.kind === "error"}
        />
        <StatCard
          label="High + critical active" icon="crosshair"
          tone={counts.kind === "loaded" && counts.data.highCriticalActive > 0 ? ((counts.data.bySeverity.critical ?? 0) > 0 ? "critical" : "high") : "muted"}
          value={alertValue((c) => c.highCriticalActive)} description={alertDescription("High or critical, still open or investigating")}
          loading={counts.kind === "loading"} unavailable={counts.kind === "error"}
        />
        <StatCard
          label="Security events" icon="pulse" tone="neon"
          value={eventsValue} description={eventsDescription}
          loading={events.kind === "loading"} unavailable={events.kind === "error"}
        />
        <StatCard
          label="Detection rules" icon="rules" tone="muted"
          value={rulesValue}
          description={rules.kind === "error" ? rules.message : rules.kind === "loaded" ? `${rules.data.enabled} enabled` : "Configured rules"}
          loading={rules.kind === "loading"} unavailable={rules.kind === "error"}
        />
      </section>

      <section aria-label="Alert lifecycle" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Open alerts" icon="inbox" tone={counts.kind === "loaded" && (counts.data.byStatus.open ?? 0) > 0 ? "medium" : "muted"}
          value={alertValue((c) => c.byStatus.open ?? 0)}
          description={counts.kind === "loaded" ? `${counts.data.acknowledgedOpen} acknowledged` : alertDescription("Status: open")}
          loading={counts.kind === "loading"} unavailable={counts.kind === "error"}
        />
        <StatCard
          label="Investigating" icon="crosshair" tone="cyan"
          value={alertValue((c) => c.byStatus.investigating ?? 0)} description={alertDescription("Alert status: investigating")}
          loading={counts.kind === "loading"} unavailable={counts.kind === "error"}
        />
        <StatCard
          label="Resolved" icon="alert" tone="neon"
          value={alertValue((c) => c.byStatus.resolved ?? 0)} description={alertDescription("Alert status: resolved")}
          loading={counts.kind === "loading"} unavailable={counts.kind === "error"}
        />
        <StatCard
          label="False positives" icon="rules" tone="muted"
          value={alertValue((c) => c.byStatus.false_positive ?? 0)} description={alertDescription("Alert status: false positive")}
          loading={counts.kind === "loading"} unavailable={counts.kind === "error"}
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Alerts by severity" note="Exact counts reported by the alerts API">
          <SectionState state={counts} reload={counts.reload} title="severity counts">
            {() => <CountBarChart data={severityData} colors={SEVERITY_COLORS} seriesLabel="Alerts by severity" emptyText="No alerts to chart yet." />}
          </SectionState>
        </ChartCard>
        <ChartCard title="Alerts by status" note="Exact counts reported by the alerts API">
          <SectionState state={counts} reload={counts.reload} title="status counts">
            {() => <CountBarChart data={statusData} colors={STATUS_COLORS} seriesLabel="Alerts by status" emptyText="No alerts to chart yet." />}
          </SectionState>
        </ChartCard>
        <ChartCard
          title={sampled ? "Alert creation times (sampled alerts only)" : "Alert creation trend"}
          note={
            sample.kind !== "loaded"
              ? `Alerts per hour or day of creation, from up to ${MAX_ALERT_SAMPLE_PAGES * 100} alerts`
              : sampled
                ? `Sample only: the ${sample.data.alerts.length} highest-priority of ${sample.data.total} alerts. The API sorts by priority, not by time, so this is not the trend of recent alerts and the other ${sample.data.total - sample.data.alerts.length} alerts are not included.`
                : `All ${sample.data.total} alerts, grouped by ${trend?.unit ?? "day"} of creation (local time)`
          }
        >
          <SectionState state={sample} reload={sample.reload} title="alert trend">
            {() => (trend ? <TrendChart trend={trend} sampled={sampled} /> : null)}
          </SectionState>
        </ChartCard>
        <ChartCard title="Events by type" note={eventsNote}>
          <SectionState state={events} reload={events.reload} title="event types">
            {() => <CountBarChart data={eventTypeData} seriesLabel="Events by type" horizontal emptyText="No security events to chart yet." />}
          </SectionState>
        </ChartCard>
        <ChartCard title="Events by source" note={eventsNote}>
          <SectionState state={events} reload={events.reload} title="event sources">
            {() => <CountBarChart data={eventSourceData} seriesLabel="Events by source" horizontal fallback="#39ff88" emptyText="No security events to chart yet." />}
          </SectionState>
        </ChartCard>
      </div>

      <section aria-labelledby="top-alerts-heading" className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="top-alerts-heading" className="font-mono text-[13px] font-bold uppercase tracking-[0.12em] text-fg">Highest-priority alerts</h2>
          <Link to="/alerts" className="text-sm font-medium text-cyan hover:underline focus-visible:outline-2 focus-visible:outline-neon">View all alerts</Link>
        </div>
        <SectionState state={sample} reload={sample.reload} title="top alerts">
          {(data) =>
            data.alerts.length === 0 ? (
              <StateMessage variant="empty" title="No alerts found.">Alerts appear here after detection runs on ingested events.</StateMessage>
            ) : (
              <AlertFeed alerts={data.alerts.slice(0, 5)} selectedId={selectedAlert} onSelect={setSelectedAlert} />
            )
          }
        </SectionState>
      </section>

      <RecentEventsPanel />
      <BackendStatusPanel backend={backend} />
      {selectedAlert && <AlertDetails alertId={selectedAlert} onClose={() => setSelectedAlert(null)} onChanged={refresh} />}
    </>
  );
}
