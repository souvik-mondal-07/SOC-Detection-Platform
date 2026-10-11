// Chart colours. Hex values mirror the tokens in index.css because SVG attributes cannot read Tailwind classes.
export const CHART = {
  grid: "#1b2a3c",
  axis: "#8ca1b8",
  cursor: "rgb(57 255 136 / 0.06)",
  neon: "#39ff88",
  cyan: "#22d3ee",
  tooltip: {
    contentStyle: { background: "#0c131d", border: "1px solid #2b3f57", borderRadius: 6, color: "#e8eef6", fontSize: 12 },
    itemStyle: { color: "#e8eef6" },
    labelStyle: { color: "#8ca1b8", fontFamily: "ui-monospace, monospace", fontSize: 11 },
  },
} as const;
