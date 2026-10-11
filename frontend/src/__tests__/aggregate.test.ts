import { describe, expect, it } from "vitest";
import { bucketByTime, countBy } from "../lib/aggregate";

describe("countBy", () => {
  it("counts and sorts by frequency, grouping blanks as unknown", () => {
    const result = countBy([{ k: "a" }, { k: "b" }, { k: "a" }, { k: null }], (i) => i.k);
    expect(result).toEqual([
      { name: "a", value: 2 },
      { name: "b", value: 1 },
      { name: "unknown", value: 1 },
    ]);
  });
  it("returns an empty list for no data (no invented values)", () => {
    expect(countBy([], () => "x")).toEqual([]);
  });
});

describe("bucketByTime", () => {
  it("returns no points when there is nothing to chart", () => {
    expect(bucketByTime([])).toEqual({ unit: "day", points: [], skipped: 0 });
  });
  it("uses hourly buckets for a short span and fills gaps with zero", () => {
    const trend = bucketByTime(["2026-10-02T10:05:00", "2026-10-02T10:50:00", "2026-10-02T12:10:00"]);
    expect(trend.unit).toBe("hour");
    expect(trend.points.map((p) => p.count)).toEqual([2, 0, 1]);
  });
  it("uses daily buckets for a long span", () => {
    const trend = bucketByTime(["2026-10-01T10:00:00", "2026-10-05T10:00:00"]);
    expect(trend.unit).toBe("day");
    expect(trend.points.map((p) => p.count)).toEqual([1, 0, 0, 0, 1]);
  });
  it("skips unparseable timestamps and reports them", () => {
    const trend = bucketByTime(["not a date", "2026-10-02T10:00:00"]);
    expect(trend.skipped).toBe(1);
    expect(trend.points.reduce((s, p) => s + p.count, 0)).toBe(1);
  });
});
