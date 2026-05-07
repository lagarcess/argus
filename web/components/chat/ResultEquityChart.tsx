"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import {
  BaselineSeries,
  ColorType,
  CrosshairMode,
  createChart,
  createSeriesMarkers,
  type BaselineData,
  type ISeriesApi,
  type LogicalRange,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { type ResultChartMarker, type ResultChartPayload } from "./types";

type ResultEquityChartProps = {
  chart: ResultChartPayload;
};

type TooltipState = {
  x: number;
  y: number;
  time: string;
  value: number;
  event?: string;
};

const CHART_POSITIVE_COLOR = "#70a38d";
const CHART_NEGATIVE_COLOR = "#b85c5c";
const CHART_POSITIVE_FILL_DARK = "rgba(112, 163, 141, 0.18)";
const CHART_POSITIVE_FILL_LIGHT = "rgba(112, 163, 141, 0.12)";
const CHART_NEGATIVE_FILL_DARK = "rgba(184, 92, 92, 0.14)";
const CHART_NEGATIVE_FILL_LIGHT = "rgba(184, 92, 92, 0.10)";
const BUY_POSITIVE_MARKER_COLOR = "#70a38d";
const SELL_NEGATIVE_MARKER_COLOR = "#b85c5c";

export default function ResultEquityChart({ chart }: ResultEquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const isDark = resolvedTheme === "dark";
  const data = useMemo<BaselineData<Time>[]>(
    () =>
      chart.series.map((point) => ({
        time: normalizeChartTime(point.time) as Time,
        value: point.value,
      })),
    [chart.series],
  );
  const eventByTime = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const marker of chart.markers ?? []) {
      const time = normalizeChartTime(marker.time);
      const existing = map.get(time) ?? [];
      map.set(time, [...existing, marker.label]);
    }
    return map;
  }, [chart.markers]);
  const dataIndexByTime = useMemo(() => {
    const map = new Map<string, number>();
    data.forEach((point, index) => {
      map.set(String(point.time), index);
    });
    return map;
  }, [data]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || data.length === 0) return;

    const chartApi = createChart(container, {
      width: container.clientWidth,
      height: 168,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "rgba(255,255,255,0.42)" : "rgba(0,0,0,0.42)",
        // TODO(launch): Provide correct TradingView attribution before launch.
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "transparent" },
        horzLines: {
          color: isDark ? "rgba(255,255,255,0.055)" : "rgba(0,0,0,0.055)",
        },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: data.some((point) => String(point.time).includes("T")),
        secondsVisible: false,
        rightOffset: 4,
        barSpacing: data.length > 240 ? 4 : 7,
        minBarSpacing: 3,
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: {
          color: isDark ? "rgba(255,255,255,0.22)" : "rgba(0,0,0,0.18)",
          labelVisible: false,
        },
        horzLine: {
          color: "transparent",
          labelVisible: false,
        },
      },
      localization: {
        priceFormatter: (price: number) =>
          new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: chart.currency ?? "USD",
            maximumFractionDigits: 0,
          }).format(price),
      },
    });

    const baseValue = chart.base_value ?? data[0]?.value ?? 0;
    const series = chartApi.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: baseValue },
      lineWidth: 2,
      topLineColor: CHART_POSITIVE_COLOR,
      bottomLineColor: CHART_NEGATIVE_COLOR,
      topFillColor1: isDark ? CHART_POSITIVE_FILL_DARK : CHART_POSITIVE_FILL_LIGHT,
      topFillColor2: "rgba(112, 163, 141, 0.00)",
      bottomFillColor1: isDark ? CHART_NEGATIVE_FILL_DARK : CHART_NEGATIVE_FILL_LIGHT,
      bottomFillColor2: "rgba(184, 92, 92, 0.00)",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(data);
    const visibleMarkerInput = {
      markers: chart.markers ?? [],
      visibleRange: chartApi.timeScale().getVisibleLogicalRange(),
      chartWidth: container.clientWidth,
      dataIndexByTime,
    };
    const markersApi = createSeriesMarkers(
      series as ISeriesApi<"Baseline", Time>,
      buildVisibleSeriesMarkers(visibleMarkerInput),
    );
    chartApi.timeScale().fitContent();
    const updateVisibleMarkers = (visibleRange: LogicalRange | null) => {
      markersApi.setMarkers(
        buildVisibleSeriesMarkers({
          markers: chart.markers ?? [],
          visibleRange,
          chartWidth: container.clientWidth,
          dataIndexByTime,
        }),
      );
    };
    chartApi.timeScale().subscribeVisibleLogicalRangeChange(updateVisibleMarkers);

    chartApi.subscribeCrosshairMove((param) => {
      if (!param.point || param.time == null) {
        setTooltip(null);
        return;
      }
      const datum = param.seriesData.get(series) as BaselineData<Time> | undefined;
      if (!datum || typeof datum.value !== "number") {
        setTooltip(null);
        return;
      }
      const time = String(param.time);
      setTooltip({
        x: param.point.x,
        y: param.point.y,
        time,
        value: datum.value,
        event: eventByTime.get(time)?.join(", "),
      });
    });

    return () => {
      setTooltip(null);
      chartApi.timeScale().unsubscribeVisibleLogicalRangeChange(updateVisibleMarkers);
      chartApi.remove();
    };
  }, [chart, data, dataIndexByTime, eventByTime, isDark]);

  if (data.length === 0) return null;

  return (
    <div className="relative border-y border-black/8 dark:border-white/8 bg-black/[0.012] dark:bg-white/[0.018]">
      <div ref={containerRef} className="h-[168px] w-full" data-testid="result-equity-chart" />
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 min-w-[148px] rounded-[10px] border border-black/10 bg-white/95 px-3 py-2 text-[11px] leading-snug text-black/70 dark:border-white/10 dark:bg-[#1d2023]/95 dark:text-white/75"
          style={{
            left: Math.min(Math.max(tooltip.x + 12, 8), 480),
            top: Math.max(tooltip.y - 10, 8),
          }}
        >
          <div className="font-medium text-black dark:text-white">{tooltip.time}</div>
          <div>
            {new Intl.NumberFormat("en-US", {
              style: "currency",
              currency: chart.currency ?? "USD",
              maximumFractionDigits: 0,
            }).format(tooltip.value)}
          </div>
          {tooltip.event && <div className="mt-1 text-black/45 dark:text-white/45">{tooltip.event}</div>}
        </div>
      )}
    </div>
  );
}

function normalizeChartTime(value: string) {
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  const dateOnly = trimmed.match(/^(\d{4}-\d{2}-\d{2})T/);
  if (dateOnly) return dateOnly[1];
  return trimmed;
}

type MarkerViewportInput = {
  chartWidth: number;
  visibleBars: number;
};

export function markerBudgetForViewport({
  chartWidth,
  visibleBars,
}: MarkerViewportInput) {
  const widthBudget = Math.max(4, Math.ceil(chartWidth / 28));
  const zoomBudget =
    visibleBars <= 45 ? 24 : visibleBars <= 90 ? 18 : visibleBars <= 180 ? 14 : 12;
  return Math.max(4, Math.min(widthBudget, zoomBudget));
}

type VisibleTradeMarkerInput = {
  markers: ResultChartMarker[];
  visibleRange: LogicalRange | null;
  chartWidth: number;
  dataIndexByTime: Map<string, number>;
};

export function selectVisibleTradeMarkers({
  markers,
  visibleRange,
  chartWidth,
  dataIndexByTime,
}: VisibleTradeMarkerInput) {
  if (markers.length <= 1) return markers;

  const from = visibleRange ? Math.floor(visibleRange.from) : 0;
  const to = visibleRange ? Math.ceil(visibleRange.to) : dataIndexByTime.size - 1;
  const visibleBars = Math.max(1, to - from + 1);
  const visibleMarkers = markers
    .map((marker, ordinal) => ({
      marker,
      ordinal,
      logicalIndex: dataIndexByTime.get(normalizeChartTime(marker.time)) ?? ordinal,
    }))
    .filter(({ logicalIndex }) => logicalIndex >= from && logicalIndex <= to)
    .sort((a, b) => a.logicalIndex - b.logicalIndex || a.ordinal - b.ordinal);

  const budget = markerBudgetForViewport({ chartWidth, visibleBars });
  if (visibleMarkers.length <= budget) {
    return visibleMarkers.map(({ marker }) => marker);
  }

  const selectedIndexes = new Set<number>();
  const step = (visibleMarkers.length - 1) / Math.max(1, budget - 1);
  for (let slot = 0; slot < budget; slot += 1) {
    selectedIndexes.add(Math.round(slot * step));
  }

  return [...selectedIndexes]
    .sort((a, b) => a - b)
    .map((index) => visibleMarkers[index]?.marker)
    .filter((marker): marker is ResultChartMarker => Boolean(marker));
}

export function buildVisibleSeriesMarkers(
  input: VisibleTradeMarkerInput,
): SeriesMarker<Time>[] {
  const visibleMarkers = selectVisibleTradeMarkers(input);
  const labeledIndexes = selectLabeledMarkerIndexes({
    markerCount: visibleMarkers.length,
    visibleRange: input.visibleRange,
    chartWidth: input.chartWidth,
  });
  return visibleMarkers.map((marker, index) =>
    toSeriesMarker(marker, labeledIndexes.has(index)),
  );
}

type LabeledMarkerInput = {
  markerCount: number;
  visibleRange: LogicalRange | null;
  chartWidth: number;
};

function selectLabeledMarkerIndexes({
  markerCount,
  visibleRange,
  chartWidth,
}: LabeledMarkerInput) {
  const indexes = new Set<number>();
  if (markerCount === 0) return indexes;

  const visibleBars = visibleRange
    ? Math.max(1, Math.ceil(visibleRange.to) - Math.floor(visibleRange.from) + 1)
    : markerCount;
  const widthBudget = Math.max(2, Math.floor(chartWidth / 170));
  const zoomBudget = visibleBars <= 45 ? 5 : visibleBars <= 90 ? 4 : 3;
  const budget = Math.min(markerCount, widthBudget, zoomBudget);

  indexes.add(0);
  if (budget > 1) indexes.add(markerCount - 1);
  if (budget > 2) indexes.add(Math.floor((markerCount - 1) / 2));
  if (budget > 3) indexes.add(Math.ceil((markerCount - 1) / 3));
  if (budget > 4) indexes.add(Math.ceil(((markerCount - 1) * 2) / 3));

  return new Set([...indexes].sort((a, b) => a - b).slice(0, budget));
}

function toSeriesMarker(marker: ResultChartMarker, showLabel: boolean): SeriesMarker<Time> {
  const isEntry = marker.type === "entry";
  return {
    time: normalizeChartTime(marker.time) as Time,
    position: isEntry ? "belowBar" : "aboveBar",
    color: isEntry ? BUY_POSITIVE_MARKER_COLOR : SELL_NEGATIVE_MARKER_COLOR,
    shape: isEntry ? "arrowUp" : "arrowDown",
    text: showLabel ? (isEntry ? "Buy" : "Sell") : undefined,
  };
}
