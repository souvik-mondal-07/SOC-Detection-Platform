import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Trend } from "../../lib/aggregate";
import { CHART } from "./theme";
import EmptyChart from "./EmptyChart";

export default function TrendChart({ trend, sampled = false }: { trend: Trend; sampled?: boolean }) {
  const total = trend.points.reduce((sum, p) => sum + p.count, 0);
  if (total === 0) {
    return <EmptyChart text="No alerts with a usable creation time to chart." />;
  }
  return (
    <div role="img" aria-label={`${sampled ? "Sampled alerts (highest priority only), created" : "Alerts created"} per ${trend.unit}: ${trend.points.map((p) => `${p.label} ${p.count}`).join(", ")}`} style={{ height: 240 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={trend.points} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: CHART.axis }} minTickGap={24} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: CHART.axis }} width={40} />
          <Tooltip {...CHART.tooltip} cursor={{ fill: CHART.cursor }} formatter={(value) => [String(value), sampled ? "Sampled alerts" : "Alerts"]} />
          <Bar dataKey="count" name={sampled ? "Sampled alerts" : "Alerts"} fill={CHART.cyan} radius={2} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
