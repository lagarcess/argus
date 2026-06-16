"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { useTranslation } from "react-i18next";
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
  presentation?: "default" | "heroDeltaEvidence";
  appearanceOverride?: "light" | "dark";
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
const CHART_POSITIVE_COLOR_DARK_EVIDENCE = "#7fb39f";
const CHART_NEGATIVE_COLOR_DARK_EVIDENCE = "#c67378";
const CHART_POSITIVE_COLOR_LIGHT = "#4f9f8f";
const CHART_NEGATIVE_COLOR_LIGHT = "#aa5555";
const CHART_POSITIVE_FILL_DARK = "rgba(112, 163, 141, 0.18)";
const CHART_POSITIVE_FILL_LIGHT = "rgba(112, 163, 141, 0.12)";
const CHART_POSITIVE_FILL_LIGHT_RESTRAINED = "rgba(91, 168, 151, 0.10)";
const CHART_NEGATIVE_FILL_DARK = "rgba(184, 92, 92, 0.14)";
const CHART_NEGATIVE_FILL_LIGHT = "rgba(184, 92, 92, 0.10)";
const CHART_NEGATIVE_FILL_LIGHT_RESTRAINED = "rgba(184, 92, 92, 0.08)";
const BUY_POSITIVE_MARKER_COLOR = "#70a38d";
const SELL_NEGATIVE_MARKER_COLOR = "#b85c5c";
const BUY_RESTRAINED_MARKER_COLOR = "rgba(112, 163, 141, 0.42)";
const SELL_RESTRAINED_MARKER_COLOR = "rgba(184, 92, 92, 0.38)";
const RESULT_CHART_ATTRIBUTION_FALLBACK = "TradingView Lightweight Charts";
export const RESULT_CHART_ATTRIBUTION_URL = "https://www.tradingview.com/";
export const RESULT_CHART_ATTRIBUTION_FOOTER_CLASS =
  "border-t border-black/[0.04] px-3 pb-2 pt-1.5 text-[10px] leading-snug text-black/45 dark:border-white/[0.06] dark:text-white/45";
const RESULT_CHART_ATTRIBUTION_HERO_FOOTER_CLASS =
  "border-t border-black/[0.035] px-3 pb-2 pt-1.5 text-[10px] leading-snug text-black/45 dark:border-white/[0.055] dark:text-white/45";

export default function ResultEquityChart({
  chart,
  appearanceOverride,
  presentation = "default",
}: ResultEquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  const { i18n } = useTranslation();
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const isDark = appearanceOverride
    ? appearanceOverride === "dark"
    : resolvedTheme === "dark";
  const chartLocale = resolveChartLocale(i18n.language);
  const isHeroDeltaEvidence = presentation === "heroDeltaEvidence";
  const chartHeight = isHeroDeltaEvidence ? 164 : 168;
  const attributionLabel = resultChartAttributionLabel(chart.attribution);
  const currencyFormatter = useMemo(
    () => chartCurrencyFormatter(chart.currency, chartLocale),
    [chart.currency, chartLocale],
  );
  const data = useMemo<BaselineData<Time>[]>(
    () =>
      chart.series.map((point) => ({
        time: chartTimeFromString(point.time),
        value: point.value,
      })),
    [chart.series],
  );
  const eventByTime = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const marker of chart.markers ?? []) {
      const time = chartTimeLookupKey(marker.time);
      const existing = map.get(time) ?? [];
      map.set(time, [...existing, marker.label]);
    }
    return map;
  }, [chart.markers]);
  const dataIndexByTime = useMemo(() => {
    const map = new Map<string, number>();
    chart.series.forEach((point, index) => {
      map.set(chartTimeLookupKey(point.time), index);
    });
    return map;
  }, [chart.series]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || data.length === 0) return;

    const chartApi = createChart(container, {
      width: container.clientWidth,
      height: chartHeight,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark
          ? "rgba(255,255,255,0.42)"
          : isHeroDeltaEvidence
            ? "rgba(0,0,0,0.52)"
            : "rgba(0,0,0,0.42)",
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: "transparent" },
        horzLines: {
          color: isDark
            ? "rgba(255,255,255,0.055)"
            : isHeroDeltaEvidence
              ? "rgba(0,0,0,0.095)"
              : "rgba(0,0,0,0.055)",
        },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: data.some((point) => typeof point.time === "number"),
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
        locale: chartLocale,
        dateFormat: "dd MMM yyyy",
        timeFormatter: (time: Time) =>
          formatChartDateLabel(time, chartLocale, "short"),
        priceFormatter: (price: number) => currencyFormatter.format(price),
      },
    });

    const baseValue = chart.base_value ?? data[0]?.value ?? 0;
    const series = chartApi.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: baseValue },
      lineWidth: 2,
      topLineColor: isHeroDeltaEvidence
        ? isDark
          ? CHART_POSITIVE_COLOR_DARK_EVIDENCE
          : CHART_POSITIVE_COLOR_LIGHT
        : CHART_POSITIVE_COLOR,
      bottomLineColor: isHeroDeltaEvidence
        ? isDark
          ? CHART_NEGATIVE_COLOR_DARK_EVIDENCE
          : CHART_NEGATIVE_COLOR_LIGHT
        : CHART_NEGATIVE_COLOR,
      topFillColor1: isDark
        ? CHART_POSITIVE_FILL_DARK
        : isHeroDeltaEvidence
          ? CHART_POSITIVE_FILL_LIGHT_RESTRAINED
          : CHART_POSITIVE_FILL_LIGHT,
      topFillColor2: "rgba(112, 163, 141, 0.00)",
      bottomFillColor1: isDark
        ? CHART_NEGATIVE_FILL_DARK
        : isHeroDeltaEvidence
          ? CHART_NEGATIVE_FILL_LIGHT_RESTRAINED
          : CHART_NEGATIVE_FILL_LIGHT,
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
      restrained: isHeroDeltaEvidence,
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
          restrained: isHeroDeltaEvidence,
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
      const time = chartTimeLookupKey(param.time);
      setTooltip({
        x: param.point.x,
        y: param.point.y,
        time: formatChartDateLabel(param.time, chartLocale),
        value: datum.value,
        event: eventByTime.get(time)?.join(", "),
      });
    });

    return () => {
      setTooltip(null);
      chartApi.timeScale().unsubscribeVisibleLogicalRangeChange(updateVisibleMarkers);
      chartApi.remove();
    };
  }, [
    chart,
    chartHeight,
    chartLocale,
    currencyFormatter,
    data,
    dataIndexByTime,
    eventByTime,
    isDark,
    isHeroDeltaEvidence,
  ]);

  if (data.length === 0) return null;

  return (
    <div
      className={
        isHeroDeltaEvidence
          ? "relative border-t border-black/[0.025] bg-transparent dark:border-white/[0.025] dark:bg-transparent"
          : "relative border-y border-black/8 bg-black/[0.012] dark:border-white/8 dark:bg-white/[0.018]"
      }
    >
      <div
        ref={containerRef}
        className="w-full"
        data-testid="result-equity-chart"
        style={{ height: chartHeight }}
      />
      <div
        className={
          isHeroDeltaEvidence
            ? RESULT_CHART_ATTRIBUTION_HERO_FOOTER_CLASS
            : RESULT_CHART_ATTRIBUTION_FOOTER_CLASS
        }
        data-testid="result-equity-chart-attribution"
      >
        <a
          className="inline-flex max-w-full text-inherit underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:focus-visible:ring-white/30"
          href={RESULT_CHART_ATTRIBUTION_URL}
          rel="noreferrer"
          target="_blank"
        >
          {attributionLabel}
        </a>
      </div>
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 min-w-[148px] rounded-[10px] border border-black/10 bg-white/95 px-3 py-2 text-[11px] leading-snug text-black/70 dark:border-white/10 dark:bg-[#1d2023]/95 dark:text-white/75"
          style={{
            left: Math.min(Math.max(tooltip.x + 12, 8), 480),
            top: Math.max(tooltip.y - 10, 8),
          }}
        >
          <div className="font-medium text-black dark:text-white">{tooltip.time}</div>
          <div>{currencyFormatter.format(tooltip.value)}</div>
          {tooltip.event && <div className="mt-1 text-black/45 dark:text-white/45">{tooltip.event}</div>}
        </div>
      )}
    </div>
  );
}

function chartTimeFromString(value: string): Time {
  const trimmed = value.trim();
  if (dateOnlyParts(trimmed)) return trimmed as Time;

  const utcTimestamp = utcTimestampFromDateTimeText(trimmed);
  return utcTimestamp == null ? (trimmed as Time) : (utcTimestamp as Time);
}

export function chartTimeLookupKey(value: Time | string) {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (dateOnlyParts(trimmed)) return trimmed;

    const dateTime = dateTimeParts(trimmed);
    if (dateTime) {
      return `${dateTime.year}-${dateTime.month}-${dateTime.day}T${dateTime.hour}:${dateTime.minute}:${dateTime.second}`;
    }

    const parsed = new Date(trimmed);
    return Number.isNaN(parsed.getTime())
      ? trimmed
      : parsed.toISOString().slice(0, 19);
  }
  if (typeof value === "number") {
    return new Date(value * 1000).toISOString().slice(0, 19);
  }
  return `${value.year}-${pad2(value.month)}-${pad2(value.day)}`;
}

function chartTimeToUtcDate(value: Time | string) {
  if (typeof value === "number") {
    return new Date(value * 1000);
  }
  if (typeof value !== "string") {
    return new Date(Date.UTC(value.year, value.month - 1, value.day));
  }

  const normalized = value.trim();
  const dateOnly = dateOnlyParts(normalized);
  if (dateOnly) {
    return new Date(
      Date.UTC(
        Number(dateOnly.year),
        Number(dateOnly.month) - 1,
        Number(dateOnly.day),
      ),
    );
  }

  const dateTime = dateTimeParts(normalized);
  if (dateTime) {
    return new Date(
      Date.UTC(
        Number(dateTime.year),
        Number(dateTime.month) - 1,
        Number(dateTime.day),
        Number(dateTime.hour),
        Number(dateTime.minute),
        Number(dateTime.second),
      ),
    );
  }

  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function utcTimestampFromDateTimeText(value: string) {
  const date = chartTimeToUtcDate(value);
  if (!date) return null;
  return Math.floor(date.getTime() / 1000);
}

function dateTimeParts(value: string) {
  if (value.length < 16 || value[10] !== "T" || value[13] !== ":") {
    return null;
  }
  const date = dateOnlyParts(value.slice(0, 10));
  const hour = fixedDigits(value.slice(11, 13), 2);
  const minute = fixedDigits(value.slice(14, 16), 2);
  const second =
    value.length >= 19 && value[16] === ":"
      ? fixedDigits(value.slice(17, 19), 2)
      : "00";
  if (!date || hour == null || minute == null || second == null) return null;
  return {
    ...date,
    hour,
    minute,
    second,
  };
}

function dateOnlyParts(value: string) {
  if (value.length !== 10 || value[4] !== "-" || value[7] !== "-") {
    return null;
  }
  const year = fixedDigits(value.slice(0, 4), 4);
  const month = fixedDigits(value.slice(5, 7), 2);
  const day = fixedDigits(value.slice(8, 10), 2);
  if (!year || !month || !day) return null;
  return { year, month, day };
}

function fixedDigits(value: string, length: number) {
  if (value.length !== length) return null;
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code < 48 || code > 57) return null;
  }
  return value;
}

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function resolveChartLocale(locale?: string | null) {
  const normalized = locale?.trim();
  if (!normalized) return "en-US";
  if (normalized.toLowerCase().startsWith("es")) return "es-419";
  if (normalized.toLowerCase() === "en") return "en-US";
  return normalized;
}

function chartCurrencyFormatter(currency: string | undefined, locale: string) {
  return new Intl.NumberFormat(resolveChartLocale(locale), {
    style: "currency",
    currency: currency ?? "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export function formatChartCurrency(
  value: number,
  currency = "USD",
  locale = "en-US",
) {
  return chartCurrencyFormatter(currency, locale).format(value);
}

export function formatChartDateLabel(
  value: Time | string,
  locale = "en-US",
  month: "short" | "long" = "long",
) {
  const date = chartTimeToUtcDate(value);
  if (!date) return String(value);
  const includesTime =
    typeof value === "number" ||
    (typeof value === "string" &&
      dateOnlyParts(value.trim()) === null &&
      dateTimeParts(value.trim()) !== null);

  return new Intl.DateTimeFormat(resolveChartLocale(locale), {
    month,
    day: "numeric",
    year: "numeric",
    ...(includesTime ? { hour: "numeric", minute: "2-digit" } : {}),
    timeZone: "UTC",
  }).format(date);
}

export function resultChartAttributionLabel(attribution?: string | null) {
  const normalized = attribution?.trim();
  return normalized || RESULT_CHART_ATTRIBUTION_FALLBACK;
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
  restrained?: boolean;
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
      logicalIndex: dataIndexByTime.get(chartTimeLookupKey(marker.time)) ?? ordinal,
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
    toSeriesMarker(marker, labeledIndexes.has(index), input.restrained),
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

function toSeriesMarker(
  marker: ResultChartMarker,
  showLabel: boolean,
  restrained = false,
): SeriesMarker<Time> {
  const isEntry = marker.type === "entry";
  return {
    time: chartTimeFromString(marker.time),
    position: isEntry ? "belowBar" : "aboveBar",
    color: isEntry
      ? restrained
        ? BUY_RESTRAINED_MARKER_COLOR
        : BUY_POSITIVE_MARKER_COLOR
      : restrained
        ? SELL_RESTRAINED_MARKER_COLOR
        : SELL_NEGATIVE_MARKER_COLOR,
    shape: isEntry ? "arrowUp" : "arrowDown",
    text: showLabel ? (isEntry ? "Buy" : "Sell") : undefined,
    ...(restrained ? { size: 0.46 } : {}),
  };
}
