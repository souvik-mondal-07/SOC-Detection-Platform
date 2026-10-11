import EmptyChart from "./EmptyChart";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CountItem } from "../../lib/aggregate";
import { CHART } from "./theme";

interface CountBarChartProps {
  data: readonly CountItem[];
  /** Fill color by category name; unknown names use `fallback`. */
  colors?: Readonly<Record<string, string>>;
  fallback?: string;
  seriesLabel: string;
  horizontal?: boolean;
  emptyText: string;
}

export const SEVERITY_COLORS: Readonly<Record<string, string>> = { low: "#4fae7a", medium: "#f5a524", high: "#f97316", critical: "#f2555a" };
export const STATUS_COLORS: Readonly<Record<string, string>> = { open: "#22d3ee", investigating: "#818cf8", resolved: "#39ff88", false_positive: "#67798f" };

const pretty = (name: string) => name.replace(/_/g, " ");

export default function CountBarChart({ data, colors = {}, fallback = "#22d3ee", seriesLabel, horizontal = false, emptyText }: CountBarChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (data.length === 0 || total === 0) {
    return <EmptyChart text={emptyText} />;
  }
  const rows = data.map((d) => ({ ...d, label: pretty(d.name) }));
  const summary = rows.map((r) => `${r.label}: ${r.value}`).join(", ");
  const height = horizontal ? Math.max(200, rows.length * 36 + 40) : 240;
  return (
    <div role="img" aria-label={`${seriesLabel}. ${summary}`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 8, right: 16, bottom: 4, left: horizontal ? 8 : 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={!horizontal} vertical={horizontal} />
          {horizontal ? (
            <>
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: CHART.axis }} />
              <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 12, fill: CHART.axis }} />
            </>
          ) : (
            <>
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: CHART.axis }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: CHART.axis }} width={40} />
            </>
          )}
          <Tooltip {...CHART.tooltip} cursor={{ fill: CHART.cursor }} formatter={(value) => [String(value), seriesLabel]} />
          <Bar dataKey="value" name={seriesLabel} radius={2} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.name} fill={Object.hasOwn(colors, r.name) ? colors[r.name] : fallback} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
