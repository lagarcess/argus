import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  RESULT_CHART_ATTRIBUTION_FOOTER_CLASS,
  RESULT_CHART_ATTRIBUTION_URL,
  buildVisibleSeriesMarkers,
  chartTimeLookupKey,
  formatChartCurrency,
  formatChartDateLabel,
  markerBudgetForViewport,
  resultChartAttributionLabel,
  selectVisibleTradeMarkers,
} from "../components/chat/ResultEquityChart";
import type { ResultChartMarker } from "../components/chat/types";
import type { LogicalRange } from "lightweight-charts";

const root = join(import.meta.dir, "..");

function marker(day: number, type: ResultChartMarker["type"] = "entry"): ResultChartMarker {
  const date = new Date(Date.UTC(2026, 0, day));
  return {
    time: date.toISOString().slice(0, 10),
    type,
    label: type === "entry" ? "Buy" : "Sell",
  };
}

describe("ResultEquityChart marker disclosure", () => {
  const logicalRange = (from: number, to: number): LogicalRange =>
    ({ from, to }) as LogicalRange;

  test("keeps the full-view marker set sparse enough to avoid label clutter", () => {
    const markers = Array.from({ length: 36 }, (_, index) =>
      marker(index + 1, index % 2 === 0 ? "entry" : "exit"),
    );

    const visible = selectVisibleTradeMarkers({
      markers,
      visibleRange: logicalRange(0, 360),
      chartWidth: 660,
      dataIndexByTime: new Map(
        markers.map((item, index) => [item.time, index]),
      ),
    });

    expect(visible.length).toBeLessThanOrEqual(12);
    expect(visible[0]?.time).toBe(markers[0]?.time);
    expect(visible.at(-1)?.time).toBe(markers.at(-1)?.time);
  });

  test("reveals more markers when the user zooms into a smaller time window", () => {
    const markers = Array.from({ length: 28 }, (_, index) =>
      marker(index + 1, index % 2 === 0 ? "entry" : "exit"),
    );
    const dataIndexByTime = new Map(
      markers.map((item, index) => [item.time, index]),
    );

    const zoomedOut = selectVisibleTradeMarkers({
      markers,
      visibleRange: logicalRange(0, 280),
      chartWidth: 660,
      dataIndexByTime,
    });
    const zoomedIn = selectVisibleTradeMarkers({
      markers,
      visibleRange: logicalRange(0, 45),
      chartWidth: 660,
      dataIndexByTime,
    });

    expect(zoomedOut.length).toBeLessThan(zoomedIn.length);
  });

  test("budgets marker density from chart width and visible bars", () => {
    expect(markerBudgetForViewport({ chartWidth: 660, visibleBars: 360 })).toBe(12);
    expect(markerBudgetForViewport({ chartWidth: 660, visibleBars: 45 })).toBe(24);
    expect(markerBudgetForViewport({ chartWidth: 320, visibleBars: 45 })).toBeLessThan(24);
  });

  test("color codes buy and sell markers with conservative labels", () => {
    const markers = Array.from({ length: 24 }, (_, index) =>
      marker(index + 1, index % 2 === 0 ? "entry" : "exit"),
    );

    const seriesMarkers = buildVisibleSeriesMarkers({
      markers,
      visibleRange: logicalRange(0, 240),
      chartWidth: 660,
      dataIndexByTime: new Map(
        markers.map((item, index) => [item.time, index]),
      ),
    });

    expect(seriesMarkers.some((item) => item.color === "#70a38d")).toBe(true);
    expect(seriesMarkers.some((item) => item.color === "#b85c5c")).toBe(true);
    expect(seriesMarkers.some((item) => item.text === "Buy")).toBe(true);
    expect(seriesMarkers.some((item) => item.text === "Sell")).toBe(true);
    expect(seriesMarkers.filter((item) => item.text).length).toBeLessThan(
      seriesMarkers.length,
    );
    expect(seriesMarkers.filter((item) => item.text).length).toBeLessThanOrEqual(4);
    expect(seriesMarkers.every((item) => item.size == null)).toBe(true);
  });

  test("can render restrained markers for the playground evidence card", () => {
    const markers = Array.from({ length: 8 }, (_, index) =>
      marker(index + 1, index % 2 === 0 ? "entry" : "exit"),
    );

    const seriesMarkers = buildVisibleSeriesMarkers({
      markers,
      visibleRange: logicalRange(0, 80),
      chartWidth: 660,
      dataIndexByTime: new Map(
        markers.map((item, index) => [item.time, index]),
      ),
      restrained: true,
    });

    expect(seriesMarkers.some((item) => item.color === "rgba(112, 163, 141, 0.42)")).toBe(true);
    expect(seriesMarkers.some((item) => item.color === "rgba(184, 92, 92, 0.38)")).toBe(true);
    expect(seriesMarkers.every((item) => item.size === 0.46)).toBe(true);
  });
});

describe("ResultEquityChart locale formatting", () => {
  test("formats Spanish chart dates and currency without fractional cents", () => {
    const formattedDate = formatChartDateLabel("2026-01-15", "es-419");
    const formattedCurrency = formatChartCurrency(12345.67, "USD", "es-419");

    expect(formattedDate).toContain("enero");
    expect(formattedDate).toStartWith("15");
    expect(formattedDate).not.toContain("January");
    expect(formattedCurrency).toBe(
      new Intl.NumberFormat("es-419", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(12345.67),
    );
    expect(formattedCurrency).not.toMatch(/[.,]\d{2}\b/);
  });
});

describe("ResultEquityChart attribution", () => {
  test("uses backend attribution text with a TradingView fallback", () => {
    expect(resultChartAttributionLabel(" TradingView Lightweight Charts ")).toBe(
      "TradingView Lightweight Charts",
    );
    expect(resultChartAttributionLabel("")).toBe("TradingView Lightweight Charts");
    expect(resultChartAttributionLabel(undefined)).toBe(
      "TradingView Lightweight Charts",
    );
    expect(RESULT_CHART_ATTRIBUTION_URL).toBe("https://www.tradingview.com/");
  });

  test("keeps attribution in a visible footer instead of overlaying chart content", () => {
    const source = readFileSync(
      join(root, "components/chat/ResultEquityChart.tsx"),
      "utf-8",
    );

    expect(source).toContain("attributionLogo: true");
    expect(source).not.toContain("attributionLogo: false");
    expect(RESULT_CHART_ATTRIBUTION_FOOTER_CLASS).toContain("border-t");
    expect(RESULT_CHART_ATTRIBUTION_FOOTER_CLASS).not.toContain("absolute");
    expect(RESULT_CHART_ATTRIBUTION_FOOTER_CLASS).not.toContain("hidden");
    expect(RESULT_CHART_ATTRIBUTION_FOOTER_CLASS).not.toContain("sr-only");
  });
});

describe("ResultEquityChart intraday timestamps", () => {
  test("preserves intraday chart timestamps as UTC timestamp values", () => {
    const intradayMarker: ResultChartMarker = {
      time: "2026-01-15T14:30:00",
      type: "entry",
      label: "Buy AAPL",
    };
    const lookupKey = chartTimeLookupKey(intradayMarker.time);
    const seriesMarkers = buildVisibleSeriesMarkers({
      markers: [intradayMarker],
      visibleRange: null,
      chartWidth: 660,
      dataIndexByTime: new Map([[lookupKey, 0]]),
    });

    expect(lookupKey).toBe("2026-01-15T14:30:00");
    expect(typeof seriesMarkers[0]?.time).toBe("number");
    expect(chartTimeLookupKey(seriesMarkers[0]!.time)).toBe(lookupKey);
    expect(formatChartDateLabel(intradayMarker.time, "en-US")).toContain("2:30");
  });
});
