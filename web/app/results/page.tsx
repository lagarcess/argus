"use client";

import React, { Suspense, useEffect, useState, useId } from "react";
import { useSearchParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { TopNav } from "@/components/TopNav";
import { fetchApi } from "@/lib/api";

// PERFORMANCE: Wrap EquityCurve in React.memo to prevent expensive SVG re-renders during unrelated parent state updates
// FEEDBACK: Use React.useId() for unique gradient IDs and add accessibility roles/labels.
const EquityCurve = React.memo(({ equityCurve, benchmarkCurve }: { equityCurve: any[], benchmarkCurve: any[] }) => {
  const gradientId = useId();

  if (!equityCurve || equityCurve.length === 0) {
    return (
      <div className="flex-1 w-full flex items-center justify-center text-[10px] uppercase tracking-widest text-on-surface-variant/50 border border-outline-variant/10 rounded-xl bg-surface-container-low/30">
        No equity vectors recorded for visualization
      </div>
    );
  }

  // Scaling Logic based on strategy vs benchmark
  const allValues = [...equityCurve, ...(benchmarkCurve || [])].map(p => p.value);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  const getPoints = (curve: any[]) => {
    return curve.map((p: any, i: number) => {
      const x = (i / (curve.length - 1)) * 100;
      const y = 100 - ((p.value - min) / range) * 80 - 10;
      return `${x},${y}`;
    });
  };

  const strategyPointsList = getPoints(equityCurve);
  const strategyPathD = `M ${strategyPointsList[0]} ` + strategyPointsList.slice(1).map(p => `L ${p}`).join(" ");
  const strategyAreaD = `${strategyPathD} L 100,100 L 0,100 Z`;

  const benchmarkPoints = benchmarkCurve && benchmarkCurve.length > 0 ? getPoints(benchmarkCurve).join(" ") : "";

  return (
    <div className="flex-1 w-full relative flex items-end pt-10 pb-4">
      {/* Y-Axis labels (Contextual to performance data) */}
      <div className="absolute left-0 top-10 bottom-4 flex flex-col justify-between text-[10px] font-mono text-on-surface-variant w-12 z-10">
          <span>${(max/1000).toFixed(1)}k</span>
          <span>${((max+min)/2000).toFixed(1)}k</span>
          <span>${(min/1000).toFixed(1)}k</span>
      </div>

      {/* Chart Area */}
      <div className="flex-1 w-full h-full relative ml-12">
          {/* Grid lines */}
          <div className="absolute inset-0 border-b border-outline-variant/10"></div>
          <div className="absolute top-[25%] left-0 w-full border-b border-outline-variant/5"></div>
          <div className="absolute top-[50%] left-0 w-full border-b border-outline-variant/5"></div>
          <div className="absolute top-[75%] left-0 w-full border-b border-outline-variant/5"></div>

          {/* SVG Line Chart */}
          <svg
            className="w-full h-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            role="img"
            aria-label="Portfolio Equity Curve vs Market Benchmark"
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#99f7ff" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#99f7ff" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Benchmark Curve (Dotted Interface) */}
            {benchmarkPoints && (
               <polyline
                 points={benchmarkPoints}
                 fill="none"
                 stroke="#ffffff44"
                 strokeWidth="1"
                 strokeDasharray="2,2"
               />
            )}

            {/* Strategy Area & Line */}
            <path d={strategyAreaD} fill={`url(#${gradientId})`} />
            <path
              d={strategyPathD}
              fill="none"
              stroke="#99f7ff"
              strokeWidth="2"
              strokeLinejoin="round"
              className="drop-shadow-[0_0_5px_rgba(153,247,255,0.8)]"
            />

            {/* Terminal Peak Dot */}
            <circle
              cx="100"
              cy={strategyPointsList[strategyPointsList.length - 1].split(',')[1]}
              r="2"
              fill="#ffffff"
              className="drop-shadow-[0_0_8px_#ffffff] animate-pulse"
            />
          </svg>

          {/* Legend Overlay */}
          <div className="absolute top-2 right-2 flex flex-col gap-1 items-end pointer-events-none">
            <div className="flex items-center gap-2">
              <div className="w-3 h-0.5 bg-primary shadow-[0_0_5px_#99f7ff]"></div>
              <span className="text-[8px] uppercase tracking-widest text-on-surface-variant font-bold">Strategy</span>
            </div>
            {benchmarkCurve && benchmarkCurve.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-px border-t border-dotted border-white/40"></div>
                <span className="text-[8px] uppercase tracking-widest text-on-surface-variant font-bold">Benchmark</span>
              </div>
            )}
          </div>

          {/* Temporal axis markers (Mocked temporal spacing) */}
          <div className="absolute -bottom-6 left-0 w-full flex justify-between text-[10px] font-mono text-on-surface-variant">
            <span>START</span>
            <span>Q1</span>
            <span>Q2</span>
            <span>Q3</span>
            <span>END</span>
          </div>
      </div>
    </div>
  );
});
EquityCurve.displayName = "EquityCurve";

function ResultsContent() {
  const searchParams = useSearchParams();
  const simId = searchParams.get("id") || "latest";
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const result = await fetchApi<any>(`/simulations/${simId}`);
        setData(result);
      } catch (err: any) {
        setError(err.message || "Failed to load simulation results");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [simId]);

  if (loading) return <div className="p-20 text-center uppercase tracking-widest font-black text-primary animate-pulse">Syncing with Argus Core...</div>;
  if (error) return <div className="p-20 text-center text-error border border-error/20 bg-error/5 m-8 rounded-xl uppercase tracking-widest font-bold">Reality Gap Error: {error}</div>;
  if (!data) return <div className="p-20 text-center text-on-surface-variant uppercase tracking-widest">No matrix found.</div>;

  const result = data.result || {};
  const metrics = result.metrics || {};
  const strategyName = data.strategies?.name || "Unnamed Strategy";
  const equityCurve = result.equity_curve || [];
  const benchmarkCurve = result.benchmark_equity_curve || [];

  return (
    <div className="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen">
      <TopNav />
      <div className="flex pt-[60px]">
        <Sidebar />

        <main className="flex-1 md:ml-64 p-8 min-h-[calc(100vh-60px)] grid grid-cols-1 lg:grid-cols-12 gap-8 tonal-shift">

          <div className="lg:col-span-12">
            <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-8">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-2 w-2 rounded-full bg-secondary shadow-[0_0_10px_#2ff801] animate-pulse"></div>
                  <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-secondary">Simulation Complete</span>
                  <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-mono">ID: {simId}</span>
                </div>
                <h1 className="text-4xl md:text-5xl font-black font-headline tracking-tighter text-on-surface uppercase drop-shadow-[0_0_15px_rgba(0,242,255,0.2)]">
                  {strategyName}
                </h1>
                <p className="text-on-surface-variant text-sm mt-2 max-w-2xl">
                  Strategy simulation completed with <span className="text-primary font-bold">Reality Gap</span> constraints applied. Output corresponds to the Argus Core network.
                </p>
              </div>

              <div className="flex gap-4">
                <button className="px-6 py-2 rounded-full border border-outline-variant/30 hover:bg-surface-container-highest transition-colors flex items-center gap-2 text-xs font-bold uppercase tracking-widest">
                  <span className="material-symbols-outlined text-sm">share</span> Share
                </button>
                <button className="px-6 py-2 rounded-full bg-primary text-on-primary-container font-bold uppercase tracking-widest text-xs flex items-center gap-2 shadow-[0_0_15px_rgba(153,247,255,0.3)] hover:shadow-[0_0_25px_rgba(153,247,255,0.5)] transition-all">
                  <span className="material-symbols-outlined text-sm">download</span> Report CSV
                </button>
              </div>
            </header>

            {/* Core Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-8">
              <div className="glass-panel p-6 rounded-xl border border-secondary/20 relative overflow-hidden">
                <div className="absolute inset-0 bg-secondary/5"></div>
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2 relative z-10">Net Return</span>
                <div className="text-3xl font-headline font-black text-secondary relative z-10">
                  {metrics.total_return_pct >= 0 ? "+" : ""}{metrics.total_return_pct?.toFixed(1)}%
                </div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Sharpe Ratio</span>
                <div className="text-3xl font-headline font-black text-on-surface">{metrics.sharpe_ratio?.toFixed(2)}</div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Alpha / Beta</span>
                <div className="text-xl font-headline font-black text-on-surface">
                   {metrics.alpha?.toFixed(3)} / {metrics.beta?.toFixed(2)}
                </div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Calmar Ratio</span>
                <div className="text-3xl font-headline font-black text-on-surface">{metrics.calmar_ratio?.toFixed(2)}</div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Max Drawdown</span>
                <div className="text-3xl font-headline font-black text-on-surface">-{Math.abs(metrics.max_drawdown_pct || 0).toFixed(1)}%</div>
              </div>
            </div>

            {/* Sub Metrics Bar */}
            <div className="flex flex-wrap gap-8 mb-8 px-6 py-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/5">
                <div>
                   <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-1">Win Rate</span>
                   <span className="text-sm font-headline font-bold text-on-surface">{metrics.win_rate_pct?.toFixed(1)}%</span>
                </div>
                <div className="w-px h-8 bg-outline-variant/10"></div>
                <div>
                   <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-1">Avg trade duration</span>
                   <span className="text-sm font-headline font-bold text-on-surface">{metrics.avg_trade_duration || "N/A"}</span>
                </div>
                <div className="w-px h-8 bg-outline-variant/10"></div>
                <div>
                   <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-1">Total Trades</span>
                   <span className="text-sm font-headline font-bold text-on-surface">{metrics.total_trades || 0}</span>
                </div>
                <div className="w-px h-8 bg-outline-variant/10"></div>
                <div>
                   <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-1">Sortino Ratio</span>
                   <span className="text-sm font-headline font-bold text-on-surface">{metrics.sortino_ratio?.toFixed(2) || "0.00"}</span>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Equity Curve (Left) */}
              <div className="lg:col-span-2 glass-panel p-6 rounded-xl border border-outline-variant/10 min-h-[400px] flex flex-col relative overflow-hidden group">
                 <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[100px] rounded-full group-hover:bg-primary/10 transition-colors pointer-events-none"></div>
                 <div className="flex justify-between items-center mb-6 relative z-10">
                   <h3 className="font-headline font-bold uppercase tracking-widest text-sm">Portfolio Equity Curve</h3>
                   <div className="flex gap-2">
                     <span className="px-3 py-1 bg-surface-container-highest rounded text-[10px] uppercase font-bold tracking-widest cursor-pointer hover:text-primary transition-colors">1H</span>
                     <span className="px-3 py-1 bg-surface-container-highest rounded text-[10px] uppercase font-bold tracking-widest cursor-pointer hover:text-primary transition-colors">4H</span>
                     <span className="px-3 py-1 bg-primary text-on-primary-container rounded text-[10px] uppercase font-bold tracking-widest shadow-sm">1D</span>
                   </div>
                 </div>

                 {/* Memoized Dynamic Equity Curve Chart */}
                 <EquityCurve equityCurve={equityCurve} benchmarkCurve={benchmarkCurve} />
              </div>

              {/* Simulation Diagnostics (Right) */}
              <div className="lg:col-span-1 space-y-4">
                 <div className="glass-panel p-6 rounded-xl border border-outline-variant/10">
                   <h3 className="font-headline font-bold uppercase tracking-widest text-sm mb-6">Reality Gap Matrix</h3>
                   <div className="space-y-4">
                     <div className="p-3 bg-surface-container-highest rounded border border-outline-variant/10">
                        <div className="text-[10px] uppercase font-bold text-on-surface-variant flex justify-between mb-1">
                          <span>Slippage Loss Estimate</span>
                          <span className="text-secondary">Low</span>
                        </div>
                        <div className="text-sm font-mono">-0.48% (Net)</div>
                     </div>
                     <div className="p-3 bg-surface-container-highest rounded border border-outline-variant/10">
                        <div className="text-[10px] uppercase font-bold text-on-surface-variant flex justify-between mb-1">
                          <span>Fee Drag</span>
                          <span className="text-error">High</span>
                        </div>
                        <div className="text-sm font-mono">-12.5% (Net)</div>
                     </div>
                     <div className="p-3 bg-surface-container-highest rounded border border-outline-variant/10">
                        <div className="text-[10px] uppercase font-bold text-on-surface-variant flex justify-between mb-1">
                          <span>Time Delay Safety (15m)</span>
                          <span className="text-secondary">Active</span>
                        </div>
                        <div className="text-sm font-mono">Missed signals: 4</div>
                     </div>
                   </div>
                 </div>

                 <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 flex flex-col justify-center items-center h-48 bg-gradient-to-br from-surface-container to-surface-container-low group overflow-hidden relative">
                    <div className="absolute inset-0 bg-primary/0 group-hover:bg-primary/5 transition-colors duration-500"></div>
                    <span className="material-symbols-outlined text-4xl text-primary mb-3 group-hover:scale-110 transition-transform duration-500">psychology</span>
                    <h3 className="font-headline font-bold uppercase tracking-widest text-sm">Deploy Matrix</h3>
                    <p className="text-[10px] text-on-surface-variant uppercase tracking-widest leading-tight mt-2 text-center">Export Strategy to Simulated Sandbox</p>
                 </div>
              </div>
            </div>

            {/* Extended Detail Table Mock */}
            <div className="mt-8 bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 overflow-hidden">
               <h3 className="font-headline font-bold uppercase tracking-widest text-sm mb-6">Simulation Trade Logs</h3>
               <table className="w-full text-left text-sm">
                  <thead className="bg-surface-container-highest text-[10px] uppercase tracking-widest text-on-surface-variant">
                    <tr>
                      <th className="px-4 py-3 font-medium">Timestamp</th>
                      <th className="px-4 py-3 font-medium">Symbol</th>
                      <th className="px-4 py-3 font-medium">Direction</th>
                      <th className="px-4 py-3 font-medium">Price In/Out</th>
                      <th className="px-4 py-3 font-medium text-right">Return %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/5">
                    {(result.trades || []).slice(0, 20).map((trade: any, i: number) => (
                      <tr key={i} className="hover:bg-surface-container-highest/30">
                        <td className="px-4 py-3 text-xs text-on-surface-variant">{trade.entry_time?.split('T')[0]}</td>
                        <td className="px-4 py-3 text-xs font-bold text-on-surface">{trade.symbol}</td>
                        <td className={`px-4 py-3 text-[10px] font-bold uppercase ${trade.pnl_pct >= 0 ? "text-secondary" : "text-error"}`}>{trade.direction}</td>
                        <td className="px-4 py-3 font-mono font-medium">{trade.entry_price?.toFixed(2)} → {trade.exit_price?.toFixed(2)}</td>
                        <td className={`px-4 py-3 text-right font-mono ${trade.pnl_pct >= 0 ? "text-secondary" : "text-error"}`}>
                          {trade.pnl_pct >= 0 ? "+" : ""}{(trade.pnl_pct * 100).toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                    {(!result.trades || result.trades.length === 0) && (
                      <tr>
                        <td colSpan={5} className="px-4 py-10 text-center text-on-surface-variant uppercase tracking-widest text-xs">No trade vectors recorded.</td>
                      </tr>
                    )}
                  </tbody>
               </table>
            </div>

          </div>
        </main>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<div>Loading Results...</div>}>
      <ResultsContent />
    </Suspense>
  );
}
