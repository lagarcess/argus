"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";

export interface DataPoint {
  time: string;
  value: number;
}

interface EquityChartProps {
  data: DataPoint[];
  colors?: {
    backgroundColor?: string;
    lineColor?: string;
    textColor?: string;
  };
}

export function EquityChart({
  data,
  colors: {
    backgroundColor = "transparent",
    lineColor = "#00f0ff", // accent-cyan
    textColor = "#94a3b8", // slate-400
  } = {}
}: EquityChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || !data.length) return;

    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: backgroundColor },
        textColor,
        fontFamily: "'Inter', sans-serif"
      },
      grid: {
        vertLines: { color: "rgba(30, 41, 59, 0.4)" }, // slate-800
        horzLines: { color: "rgba(30, 41, 59, 0.4)" },
      },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
    });

    chart.timeScale().fitContent();

    // @ts-expect-error - addAreaSeries exists but TS definitions might be outdated or strict
    const newSeries = chart.addAreaSeries({
      lineColor,
      topColor: 'rgba(0, 240, 255, 0.2)',
      bottomColor: 'rgba(0, 240, 255, 0.0)',
      lineWidth: 2,
    });

    // Lightweight charts requires time to be a string formatted specifically or unix timestamp
    const formattedData = data.map(d => ({
        // We ensure data strings are formatted correctly for TV
        time: d.time.split('T')[0] as string,
        value: d.value
    }));

    // Data must be sorted for TV to render
    formattedData.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

    newSeries.setData(formattedData);

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, backgroundColor, lineColor, textColor]);

  return <div ref={chartContainerRef} className="w-full h-full" />;
}
