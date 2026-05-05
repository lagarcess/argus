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
  type Time,
} from "lightweight-charts";
import { type ResultChartPayload } from "./types";

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
    const map = new Map<string, string>();
    for (const marker of chart.markers ?? []) {
      map.set(normalizeChartTime(marker.time), marker.label);
    }
    return map;
  }, [chart.markers]);

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
        attributionLogo: true,
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
    createSeriesMarkers(
      series as ISeriesApi<"Baseline", Time>,
      (chart.markers ?? []).map((marker) => ({
        time: normalizeChartTime(marker.time) as Time,
        position: marker.type === "entry" ? "belowBar" : "aboveBar",
        color: marker.type === "entry" ? CHART_POSITIVE_COLOR : CHART_NEGATIVE_COLOR,
        shape: marker.type === "entry" ? "arrowUp" : "arrowDown",
        text: marker.type === "entry" ? "Buy" : "Sell",
      })),
    );
    chartApi.timeScale().fitContent();

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
        event: eventByTime.get(time),
      });
    });

    return () => {
      setTooltip(null);
      chartApi.remove();
    };
  }, [chart, data, eventByTime, isDark]);

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
