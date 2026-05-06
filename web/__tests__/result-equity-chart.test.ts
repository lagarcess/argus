import { describe, expect, test } from "bun:test";

import {
  buildVisibleSeriesMarkers,
  markerBudgetForViewport,
  selectVisibleTradeMarkers,
} from "../components/chat/ResultEquityChart";
import type { ResultChartMarker } from "../components/chat/types";
import type { LogicalRange } from "lightweight-charts";

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
  });
});
