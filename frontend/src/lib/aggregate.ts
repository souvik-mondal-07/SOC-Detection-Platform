// Pure helpers that turn API records into chart data. They only count what they are given.

export interface CountItem {
  name: string;
  value: number;
}

export function countBy<T>(items: readonly T[], key: (item: T) => string | null | undefined): CountItem[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const name = key(item)?.trim() || "unknown";
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value || a.name.localeCompare(b.name));
}

export type TrendUnit = "hour" | "day";

export interface TrendPoint {
  start: number;
  label: string;
  count: number;
}

export interface Trend {
  unit: TrendUnit;
  points: TrendPoint[];
  /** Timestamps that could not be parsed and were left out. */
  skipped: number;
}

const HOUR = 3_600_000;
export const MAX_TREND_POINTS = 60;

function floorTo(date: Date, unit: TrendUnit): Date {
  const copy = new Date(date);
  if (unit === "hour") copy.setMinutes(0, 0, 0);
  else copy.setHours(0, 0, 0, 0);
  return copy;
}

function nextBucket(date: Date, unit: TrendUnit): Date {
  const copy = new Date(date);
  if (unit === "hour") copy.setHours(copy.getHours() + 1);
  else copy.setDate(copy.getDate() + 1);
  return copy;
}

function labelFor(date: Date, unit: TrendUnit): string {
  return unit === "hour"
    ? date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Groups timestamps into local-time buckets: hourly when they span 48 h or less, otherwise daily. Gaps are filled with 0. */
export function bucketByTime(timestamps: readonly string[]): Trend {
  const times: number[] = [];
  let skipped = 0;
  for (const value of timestamps) {
    const t = new Date(value).getTime();
    if (Number.isNaN(t)) skipped += 1;
    else times.push(t);
  }
  if (times.length === 0) return { unit: "day", points: [], skipped };

  const min = Math.min(...times);
  const max = Math.max(...times);
  const unit: TrendUnit = max - min <= 48 * HOUR ? "hour" : "day";

  const counts = new Map<number, number>();
  for (const t of times) {
    const key = floorTo(new Date(t), unit).getTime();
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const points: TrendPoint[] = [];
  const end = floorTo(new Date(max), unit);
  for (let cursor = floorTo(new Date(min), unit); cursor <= end; cursor = nextBucket(cursor, unit)) {
    points.push({ start: cursor.getTime(), label: labelFor(cursor, unit), count: counts.get(cursor.getTime()) ?? 0 });
  }
  return { unit, points: points.slice(-MAX_TREND_POINTS), skipped };
}
