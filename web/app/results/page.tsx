"use client";

import React, { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { TopNav } from "@/components/TopNav";

// PERFORMANCE: Wrap EquityCurve in React.memo to prevent expensive SVG re-renders during unrelated parent state updates
const EquityCurve = React.memo(() => {
  return (
    <div className="flex-1 w-full relative flex items-end pt-10 pb-4">
      {/* Y-Axis labels */}
      <div className="absolute left-0 top-10 bottom-4 flex flex-col justify-between text-[10px] font-mono text-on-surface-variant w-12 z-10">
          <span>$12.5k</span>
          <span>$11.8k</span>
          <span>$11.0k</span>
          <span>$10.4k</span>
          <span>$10.0k</span>
      </div>

      {/* Chart Area */}
      <div className="flex-1 w-full h-full relative ml-12">
          {/* Grid lines */}
          <div className="absolute inset-0 border-b border-outline-variant/10"></div>
          <div className="absolute top-[25%] left-0 w-full border-b border-outline-variant/5"></div>
          <div className="absolute top-[50%] left-0 w-full border-b border-outline-variant/5"></div>
          <div className="absolute top-[75%] left-0 w-full border-b border-outline-variant/5"></div>

          {/* SVG Line Chart Mock */}
          <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#99f7ff" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#99f7ff" stopOpacity="0.0" />
              </linearGradient>
            </defs>
            <path
              d="M 0 100 L 0 70 L 10 75 L 20 60 L 30 65 L 40 40 L 50 45 L 60 20 L 70 30 L 80 15 L 90 25 L 100 5 L 100 100 Z"
              fill="url(#lineGrad)"
            />
            <path
              d="M 0 70 L 10 75 L 20 60 L 30 65 L 40 40 L 50 45 L 60 20 L 70 30 L 80 15 L 90 25 L 100 5"
              fill="none" stroke="#99f7ff" strokeWidth="2" strokeLinejoin="round"
              className="drop-shadow-[0_0_5px_rgba(153,247,255,0.8)]"
            />

            {/* Peak dot */}
            <circle cx="100" cy="5" r="3" fill="#ffffff" className="drop-shadow-[0_0_8px_#ffffff] animate-pulse" />
          </svg>

          {/* X-axis labels */}
          <div className="absolute -bottom-6 left-0 w-full flex justify-between text-[10px] font-mono text-on-surface-variant">
            <span>Jan</span>
            <span>Feb</span>
            <span>Mar</span>
            <span>Apr</span>
            <span>May</span>
            <span>Jun</span>
          </div>
      </div>
    </div>
  );
});
EquityCurve.displayName = "EquityCurve";

function ResultsContent() {
  const searchParams = useSearchParams();
  const simId = searchParams.get("id");

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
                  <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-mono">ID: {simId || "LATEST_01"}</span>
                </div>
                <h1 className="text-4xl md:text-5xl font-black font-headline tracking-tighter text-on-surface uppercase drop-shadow-[0_0_15px_rgba(0,242,255,0.2)]">
                  Backtest Results
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
                <div className="text-3xl font-headline font-black text-secondary relative z-10">+24.5%</div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Max Drawdown</span>
                <div className="text-3xl font-headline font-black text-on-surface">-8.2%</div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Win Rate</span>
                <div className="text-3xl font-headline font-black text-on-surface">62.4%</div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Sharpe Ratio</span>
                <div className="text-3xl font-headline font-black text-on-surface">2.14</div>
              </div>
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 col-span-2 md:col-span-4 lg:col-span-1">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Total Trades</span>
                <div className="text-3xl font-headline font-black text-on-surface">1,048</div>
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

                 {/* Visual Mock for Equity Curve Chart */}
                 <EquityCurve />
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
               <h3 className="font-headline font-bold uppercase tracking-widest text-sm mb-6">Last 10 Simulations</h3>
               <table className="w-full text-left text-sm">
                  <thead className="bg-surface-container-highest text-[10px] uppercase tracking-widest text-on-surface-variant">
                    <tr>
                      <th className="px-4 py-3 font-medium">Date</th>
                      <th className="px-4 py-3 font-medium">Action</th>
                      <th className="px-4 py-3 font-medium">Price</th>
                      <th className="px-4 py-3 font-medium">Shares/Qty</th>
                      <th className="px-4 py-3 font-medium text-right">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/5">
                    {/* Dummy Data */}
                    <tr className="hover:bg-surface-container-highest/30">
                      <td className="px-4 py-3 text-xs text-on-surface-variant">2026-06-15 14:30</td>
                      <td className="px-4 py-3 text-[10px] font-bold uppercase text-error">Exit (Long)</td>
                      <td className="px-4 py-3 font-mono font-medium">3,450.20</td>
                      <td className="px-4 py-3 font-mono">2.45</td>
                      <td className="px-4 py-3 text-right text-secondary font-mono">+$245.10</td>
                    </tr>
                    <tr className="hover:bg-surface-container-highest/30">
                      <td className="px-4 py-3 text-xs text-on-surface-variant">2026-06-14 09:15</td>
                      <td className="px-4 py-3 text-[10px] font-bold uppercase text-secondary">Entry (Long)</td>
                      <td className="px-4 py-3 font-mono font-medium">3,350.15</td>
                      <td className="px-4 py-3 font-mono">2.45</td>
                      <td className="px-4 py-3 text-right text-on-surface-variant font-mono">--</td>
                    </tr>
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
