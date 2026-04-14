"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, AreaSeries, LineSeries } from "lightweight-charts";

export interface DataPoint {
  time: string;
  value: number;
}

export interface ChartSeries {
  label: string;
  data: DataPoint[];
  color: string;
  type: 'area' | 'line';
  lineWidth?: number;
}

interface EquityChartProps {
  series: ChartSeries[];
  backgroundColor?: string;
  textColor?: string;
}

export function EquityChart({
  series,
  backgroundColor = "transparent",
  textColor = "#94a3b8", // slate-400
}: EquityChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || !series.length) return;

    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
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
      height: 350,
    });

    chartRef.current = chart;

    series.forEach((s) => {
      const formattedData = s.data.map(d => ({
        time: d.time.split('T')[0] as string,
        value: d.value
      })).sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

      if (s.type === 'area') {
        const areaSeries = chart.addSeries(AreaSeries, {
          lineColor: s.color,
          topColor: `${s.color}33`, // 20% opacity
          bottomColor: `${s.color}00`, // 0% opacity
          lineWidth: (s.lineWidth || 2) as 1 | 2 | 3 | 4,
          title: s.label,
        });
        areaSeries.setData(formattedData);
      } else {
        const lineSeries = chart.addSeries(LineSeries, {
          color: s.color,
          lineWidth: (s.lineWidth || 2) as 1 | 2 | 3 | 4,
          title: s.label,
        });
        lineSeries.setData(formattedData);
      }
    });

    chart.timeScale().fitContent();

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [series, backgroundColor, textColor]);

  return <div ref={chartContainerRef} className="w-full h-full" />;
}
