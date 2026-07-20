import { describe, expect, test } from "bun:test";
import {
  deriveResultChartRanges,
  resolveCustomResultChartRange,
  summarizeVisibleResultChartRange,
} from "../lib/result-chart-range";
import type {
  ResultChartMarker,
  ResultChartPoint,
} from "../components/chat/types";

const DAY = 24 * 60 * 60 * 1000;

function timedSeries(
  start: string,
  count: number,
  stepMinutes: number,
): ResultChartPoint[] {
  const first = Date.parse(start);
  return Array.from({ length: count }, (_, index) => ({
    time: new Date(first + index * stepMinutes * 60_000)
      .toISOString()
      .slice(0, 19),
    value: 1000 + index,
  }));
}

function dailySeries(start: string, count: number): ResultChartPoint[] {
  const first = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: count }, (_, index) => ({
    time: new Date(first + index * DAY).toISOString().slice(0, 10),
    value: 1000 + index,
  }));
}

function keys(series: ResultChartPoint[], duration?: string) {
  return deriveResultChartRanges(series, {
    minimum_visible_observations: 6,
    ...(duration ? { minimum_meaningful_duration: duration } : {}),
  }).map((range) => range.key);
}

describe("deriveResultChartRanges", () => {
  test("two-week hourly hold exposes 1D, 1W, and ALL", () => {
    expect(
      keys(timedSeries("2026-01-01T00:00:00Z", 14 * 24 + 1, 60), "P1M"),
    ).toEqual(["1D", "1W", "ALL"]);
  });

  test("three-year daily hold caps the four shortest meaningful ranges then ALL", () => {
    expect(keys(dailySeries("2023-01-01", 1096), "P1M")).toEqual([
      "1M",
      "3M",
      "YTD",
      "1Y",
      "ALL",
    ]);
  });

  test("monthly recurring policy suppresses ranges shorter than two months", () => {
    expect(keys(dailySeries("2024-01-01", 731), "P2M")).toEqual([
      "3M",
      "YTD",
      "1Y",
      "ALL",
    ]);
  });

  test("short run falls back to observation-qualified shorter ranges", () => {
    // 61 daily points under a six-month capability duration: nothing meets
    // P6M, so the data-eligible shorter presets return. A 1D window holds only
    // two daily observations, so the six-observation rule keeps it hidden.
    expect(keys(dailySeries("2026-01-01", 61), "P6M")).toEqual([
      "1W",
      "1M",
      "ALL",
    ]);
  });

  test.each([90, 120, 240])(
    "dense intraday spacing %s minutes qualifies 1D without any allowlist",
    (stepMinutes) => {
      const count = Math.floor((14 * 24 * 60) / stepMinutes) + 1;
      expect(keys(timedSeries("2026-01-01T00:00:00Z", count, stepMinutes))).toEqual([
        "1D",
        "1W",
        "ALL",
      ]);
    },
  );

  test.each([360, 720])(
    "sparse intraday spacing %s minutes drops 1D via the observation minimum",
    (stepMinutes) => {
      const count = Math.floor((14 * 24 * 60) / stepMinutes) + 1;
      expect(keys(timedSeries("2026-01-01T00:00:00Z", count, stepMinutes))).toEqual([
        "1W",
        "ALL",
      ]);
    },
  );

  test("legacy and malformed policies use observation-only behavior", () => {
    const series = dailySeries("2024-01-01", 731);
    const legacy = deriveResultChartRanges(series).map((range) => range.key);
    const malformed = deriveResultChartRanges(series, {
      minimum_visible_observations: 6,
      minimum_meaningful_duration: "one month",
    }).map((range) => range.key);
    expect(malformed).toEqual(legacy);
    expect(legacy).toEqual(["1W", "1M", "3M", "YTD", "ALL"]);
  });

  test("YTD anchors to the latest observation and disappears when it duplicates ALL", () => {
    const distinct = deriveResultChartRanges(dailySeries("2025-01-01", 425));
    expect(distinct.map((range) => range.key)).toContain("YTD");
    const duplicate = deriveResultChartRanges(dailySeries("2026-01-01", 60));
    expect(duplicate.map((range) => range.key)).not.toContain("YTD");
  });

  test("calendar month subtraction clamps to leap day", () => {
    const oneMonth = deriveResultChartRanges(dailySeries("2024-01-01", 91), {
      minimum_visible_observations: 6,
      minimum_meaningful_duration: "P1M",
    }).find((range) => range.key === "1M");
    expect(oneMonth?.startTime).toBe("2024-02-29");
    expect(oneMonth?.endTime).toBe("2024-03-31");
  });

  test("fewer than six valid points hides every range control", () => {
    expect(deriveResultChartRanges(dailySeries("2026-01-01", 5))).toEqual([]);
  });

  test("a short series with no qualifying window still restores ALL", () => {
    expect(keys(dailySeries("2026-01-01", 8))).toEqual(["ALL"]);
  });

  test("normalization does not rewrite the supplied render series", () => {
    const series = [
      ...dailySeries("2026-01-01", 8),
      { time: "invalid", value: 50 },
      { time: "2026-01-02", value: 999 },
    ];
    const before = JSON.stringify(series);
    deriveResultChartRanges(series);
    expect(JSON.stringify(series)).toBe(before);
  });

  test("invalid timestamps are excluded from eligibility math", () => {
    const series = [
      ...dailySeries("2026-01-01", 5),
      { time: "not a date", value: 1 },
    ];
    expect(deriveResultChartRanges(series)).toEqual([]);
  });
});

describe("resolveCustomResultChartRange", () => {
  test("custom dates clamp and include the complete UTC end date", () => {
    const result = resolveCustomResultChartRange(
      timedSeries("2026-01-01T00:00:00Z", 10 * 24, 60),
      "2025-12-01",
      "2027-01-01",
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.range.startTime).toBe("2026-01-01T00:00:00");
      expect(result.range.endTime).toBe("2026-01-10T23:00:00");
    }
  });

  test("a mid-series custom day keeps intraday observations inside its UTC day", () => {
    const result = resolveCustomResultChartRange(
      timedSeries("2026-01-01T00:00:00Z", 10 * 24, 60),
      "2026-01-05",
      "2026-01-08",
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.range.startTime).toBe("2026-01-05T00:00:00");
      expect(result.range.endTime).toBe("2026-01-08T23:00:00");
    }
  });

  test("invalid custom input returns typed errors", () => {
    const series = dailySeries("2026-01-01", 10);
    expect(resolveCustomResultChartRange(series, "", "2026-01-03")).toEqual({
      ok: false,
      error: "missing_date",
    });
    expect(
      resolveCustomResultChartRange(series, "2026-01-04", "2026-01-03"),
    ).toEqual({
      ok: false,
      error: "start_after_end",
    });
    expect(
      resolveCustomResultChartRange(series, "2026-01-03", "2026-01-03"),
    ).toEqual({
      ok: false,
      error: "insufficient_observations",
    });
  });

  test("a range entirely outside the observations is insufficient", () => {
    const series = dailySeries("2026-01-01", 10);
    expect(
      resolveCustomResultChartRange(series, "2027-05-01", "2027-06-01"),
    ).toEqual({
      ok: false,
      error: "insufficient_observations",
    });
  });
});

describe("summarizeVisibleResultChartRange", () => {
  test("visible extrema preserve the earliest tied timestamp", () => {
    const summary = summarizeVisibleResultChartRange({
      series: [
        { time: "2026-01-01", value: 10 },
        { time: "2026-01-02", value: 15 },
        { time: "2026-01-03", value: 15 },
        { time: "2026-01-04", value: 5 },
        { time: "2026-01-05", value: 5 },
      ],
      startIndex: 0,
      endIndex: 4,
    });
    expect(summary?.peak).toEqual({ time: "2026-01-02", value: 15 });
    expect(summary?.low).toEqual({ time: "2026-01-04", value: 5 });
  });

  test("visible events are typed and deterministically capped at twenty", () => {
    const series = dailySeries("2026-01-01", 42);
    const markers: ResultChartMarker[] = series.map((point, index) => ({
      time: point.time,
      type: index % 2 === 0 ? "entry" : "exit",
      label: "prose must not drive accessible copy",
      symbols: ["AAPL"],
    }));
    const summary = summarizeVisibleResultChartRange({
      series,
      markers,
      startIndex: 0,
      endIndex: 41,
    });
    expect(summary?.suppliedEventCount).toBe(42);
    expect(summary?.displayedEvents).toHaveLength(20);
    expect(summary?.displayedEvents[0]?.sourceIndex).toBe(0);
    expect(summary?.displayedEvents.at(-1)?.sourceIndex).toBe(41);
    expect(summary?.eventListSampled).toBe(true);
    expect(summary?.markerSummary).toBeUndefined();
  });

  test("markers outside the visible range are excluded and order is chronological", () => {
    const series = dailySeries("2026-01-01", 20);
    const markers: ResultChartMarker[] = [
      { time: "2026-01-18", type: "exit", label: "Sell", symbols: ["AAPL"] },
      { time: "2026-01-02", type: "entry", label: "Buy", symbols: ["AAPL"] },
      { time: "2026-03-01", type: "entry", label: "Buy", symbols: ["AAPL"] },
      { time: "garbage", type: "entry", label: "Buy", symbols: ["AAPL"] },
    ];
    const summary = summarizeVisibleResultChartRange({
      series,
      markers,
      startIndex: 0,
      endIndex: 19,
    });
    expect(summary?.suppliedEventCount).toBe(2);
    expect(summary?.displayedEvents.map((event) => event.sourceIndex)).toEqual([
      1, 0,
    ]);
    expect(summary?.eventListSampled).toBe(false);
  });

  test("passes the backend marker summary through untouched when supplied", () => {
    const series = dailySeries("2026-01-01", 10);
    const summary = summarizeVisibleResultChartRange({
      series,
      markers: [],
      markerSummary: { total_groups: 124, included_groups: 80, sampled: true },
      startIndex: 0,
      endIndex: 9,
    });
    expect(summary?.markerSummary).toEqual({
      total_groups: 124,
      included_groups: 80,
      sampled: true,
    });
    expect(summary?.suppliedEventCount).toBe(0);
    expect(summary?.displayedEvents).toEqual([]);
  });

  test("returns null when the visible range has no valid points", () => {
    expect(
      summarizeVisibleResultChartRange({
        series: [{ time: "invalid", value: 1 }],
        startIndex: 0,
        endIndex: 0,
      }),
    ).toBeNull();
    expect(
      summarizeVisibleResultChartRange({
        series: dailySeries("2026-01-01", 3),
        startIndex: 5,
        endIndex: 9,
      }),
    ).toBeNull();
  });
});
