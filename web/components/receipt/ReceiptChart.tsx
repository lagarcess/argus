"use client";

import { useEffect, useRef, useState } from "react";
import {
  BaselineSeries,
  ColorType,
  createChart,
  type UTCTimestamp,
} from "lightweight-charts";
import type { PublicReceiptVisual } from "@/lib/public-receipt-contract";

type ReceiptChartProps = {
  visual: PublicReceiptVisual;
};

const POSITIVE_LINE = "#5ba897";
const NEGATIVE_LINE = "#c67378";

function chartTime(value: string): UTCTimestamp | string {
  // Daily points stay as business days so the axis reads as dates, not clocks.
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return Math.floor(parsed / 1000) as UTCTimestamp;
}

function documentIsDark(): boolean {
  if (typeof document === "undefined") return true;
  return document.documentElement.classList.contains("dark");
}

/**
 * A read-only chart of frozen data. No range controls, no tooltip, no markers:
 * a receipt is a record, and the numbers a viewer needs are in the metric rows
 * beside it.
 *
 * Appearance is read from the document class rather than a prop, because the
 * page around it is server-rendered and the theme is only known in the browser.
 */
export default function ReceiptChart({ visual }: ReceiptChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    setIsDark(documentIsDark());
    const observer = new MutationObserver(() => setIsDark(documentIsDark()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || visual.series.length < 2) return;
    const chart = createChart(container, {
      autoSize: true,
      height: 180,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "rgba(255,255,255,0.42)" : "rgba(0,0,0,0.45)",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "transparent" },
        horzLines: {
          color: isDark ? "rgba(255,255,255,0.055)" : "rgba(0,0,0,0.06)",
        },
      },
      rightPriceScale: {
        borderVisible: false,
        // Generous top margin so the highest price label is not clipped by the
        // chart's own top edge at phone height.
        scaleMargins: { top: 0.22, bottom: 0.16 },
      },
      timeScale: { borderVisible: false, secondsVisible: false },
      handleScroll: false,
      handleScale: false,
      crosshair: { horzLine: { visible: false }, vertLine: { visible: false } },
    });
    const baseValue = visual.base_value ?? visual.series[0]?.value ?? 0;
    const series = chart.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: baseValue },
      lineWidth: 2,
      topLineColor: POSITIVE_LINE,
      bottomLineColor: NEGATIVE_LINE,
      topFillColor1: "rgba(91, 168, 151, 0.16)",
      topFillColor2: "rgba(91, 168, 151, 0.00)",
      bottomFillColor1: "rgba(198, 115, 120, 0.14)",
      bottomFillColor2: "rgba(198, 115, 120, 0.00)",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    series.setData(
      visual.series.map((point) => ({
        time: chartTime(point.time),
        value: point.value,
      })),
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [visual, isDark]);

  return <div ref={containerRef} className="h-[180px] w-full" />;
}
