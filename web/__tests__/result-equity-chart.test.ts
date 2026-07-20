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
  resultChartMarkerDisplayLabel,
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

  test("localizes marker labels from structured entry and exit types", () => {
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
      markerLabels: {
        entry: "Comprar",
        exit: "Vender",
      },
    });

    expect(seriesMarkers.some((item) => item.text === "Comprar")).toBe(true);
    expect(seriesMarkers.some((item) => item.text === "Vender")).toBe(true);
    expect(seriesMarkers.some((item) => item.text === "Buy")).toBe(false);
    expect(seriesMarkers.some((item) => item.text === "Sell")).toBe(false);
    expect(
      resultChartMarkerDisplayLabel(
        {
          time: "2026-01-01",
          type: "entry",
          label: "Buy AAPL",
          symbols: ["AAPL", "MSFT"],
        },
        { entry: "Comprar", exit: "Vender" },
      ),
    ).toBe("Comprar AAPL, MSFT");
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

describe("ResultEquityChart adaptive range integration", () => {
  const chartSource = readFileSync(
    join(root, "components/chat/ResultEquityChart.tsx"),
    "utf-8",
  );

  test("wires the pure range policy into the chart adapter", () => {
    expect(chartSource).toContain("deriveResultChartRanges");
    expect(chartSource).toContain("resolveCustomResultChartRange");
    expect(chartSource).toContain("summarizeVisibleResultChartRange");
    expect(chartSource).toContain("hasIntradayObservations");
    expect(chartSource).toContain("setVisibleLogicalRange");
    expect(chartSource).toContain("subscribeVisibleLogicalRangeChange");
    expect(chartSource).toContain("<ResultChartExploration");
    expect(chartSource).not.toContain("buy_and_hold");
    expect(chartSource).not.toContain("dca_accumulation");
    expect(chartSource).not.toContain("fetch(");
  });

  test("keeps the semantic exploration component typed and display-label free", () => {
    const explorationSource = readFileSync(
      join(root, "components/chat/ResultChartExploration.tsx"),
      "utf-8",
    );

    expect(explorationSource).toContain("aria-pressed");
    expect(explorationSource).toContain('role="status"');
    // Quiet segmented switcher: 44px hit targets in the conventional order.
    expect(explorationSource).toContain("min-h-11");
    expect(explorationSource).toContain('"1D", "1W", "1M", "3M", "YTD", "1Y"');
    expect(explorationSource).toContain("showTimes");
    expect(explorationSource).toContain("result-chart-range-");
    expect(explorationSource).toContain("result-chart-details-toggle");
    expect(explorationSource).toContain("result-chart-custom-indicator");
    expect(explorationSource).toContain("result-chart-custom-start");
    expect(explorationSource).toContain("result-chart-custom-end");
    expect(explorationSource).toContain("result-chart-custom-apply");
    expect(explorationSource).toContain("result-chart-custom-cancel");
    expect(explorationSource).toContain("result-chart-custom-error");
    expect(explorationSource).toContain("result-chart-reset");
    expect(explorationSource).toContain("result-chart-visible-period");
    expect(explorationSource).toContain("result-chart-peak");
    expect(explorationSource).toContain("result-chart-low");
    expect(explorationSource).toContain("result-chart-event-count");
    expect(explorationSource).toContain("result-chart-event-list");
    expect(explorationSource).toContain("result-chart-event-sampling");
    expect(explorationSource).toContain("result-chart-marker-cap");
    // Accessible copy comes from typed marker fields, never backend prose.
    expect(explorationSource).not.toContain("marker.label");
    expect(explorationSource).not.toContain("buy_and_hold");
    expect(explorationSource).not.toContain("dca_accumulation");
    expect(explorationSource).not.toContain("fetch(");
  });

  test("localizes every range control and summary string in English and Spanish", () => {
    const en = JSON.parse(
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
    );
    const es = JSON.parse(
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    );
    const presetKeys = ["1D", "1W", "1M", "3M", "YTD", "1Y", "ALL"];
    const rangeKeys = [
      "group_label",
      "details",
      "custom",
      "custom_heading",
      "apply",
      "cancel",
      "reset",
      "start_date",
      "end_date",
      "error_missing_date",
      "error_start_after_end",
      "error_insufficient_observations",
      "visible_period",
      "peak_label",
      "low_label",
      "event_count_one",
      "event_count_other",
      "no_events",
      "event_sampling",
      "marker_cap",
    ];

    for (const catalog of [en, es]) {
      const range = catalog.chat.result_chart.range;
      for (const preset of presetKeys) {
        expect(typeof range.presets[preset]).toBe("string");
        expect(range.presets[preset].length).toBeGreaterThan(0);
      }
      for (const key of rangeKeys) {
        expect(typeof range[key]).toBe("string");
        expect(range[key].length).toBeGreaterThan(0);
      }
    }

    // Spanish prose must be translated, not English fallback copy.
    for (const key of rangeKeys) {
      expect(es.chat.result_chart.range[key]).not.toBe(
        en.chat.result_chart.range[key],
      );
    }
    expect(en.chat.result_chart.range.visible_period).toContain("{{start}}");
    expect(es.chat.result_chart.range.visible_period).toContain("{{start}}");
    expect(en.chat.result_chart.range.event_sampling).toContain("{{shown}}");
    expect(es.chat.result_chart.range.event_sampling).toContain("{{shown}}");
    expect(en.chat.result_chart.range.marker_cap).toContain("{{included}}");
    expect(es.chat.result_chart.range.marker_cap).toContain("{{included}}");
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
