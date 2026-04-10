"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ArrowLeft, TrendingUp, TrendingDown, Percent, DollarSign, Activity } from "lucide-react";
import Link from "next/link";
// In real app, import from lib/api
import { mockGetBacktest } from "@/lib/mockApi";
import { EquityChart } from "@/components/EquityChart";

export default function BacktestResultsPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: backtest, isLoading } = useQuery({
    queryKey: ['backtest', id],
    queryFn: () => mockGetBacktest(id),
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <span className="w-8 h-8 border-2 border-slate-800 border-t-cyan-400 rounded-full animate-spin" />
        <p className="text-slate-400 text-sm animate-pulse tracking-widest uppercase">Crunching Reality Gaps...</p>
      </div>
    );
  }

  if (!backtest) {
    return (
      <div className="text-center py-20 text-slate-400">Backtest not found</div>
    );
  }

  const stats = backtest.results;
  const capital = (backtest.config_snapshot?.capital as number) || 100000;
  const metrics = [
    { label: "Net Return", value: `${stats.total_return_pct.toFixed(2)}%`, icon: Percent },
    { label: "Absolute Profit", value: `$${((stats.total_return_pct / 100) * capital).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`, icon: DollarSign },
    { label: "Win Rate", value: `${stats.win_rate.toFixed(1)}%`, icon: TrendingUp },
    { label: "Max Drawdown", value: `${stats.max_drawdown_pct.toFixed(2)}%`, icon: TrendingDown },
    { label: "Sharpe Ratio", value: stats.sharpe_ratio.toFixed(2), icon: Activity },
    { label: "Total Trades", value: stats.trades?.length || 0, icon: Activity },
  ];

  const startDate = new Date((backtest.config_snapshot?.period_start as string) || Date.now());
  const tf = (backtest.config_snapshot?.timeframe as string) || "1D";
  const msPerCandle = tf === "1Min" ? 60000 : tf === "5Min" ? 300000 : tf === "15Min" ? 900000 : tf === "1H" ? 3600000 : 86400000;
  const startMs = startDate.getTime();

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-20">
      <Link href="/history" className="inline-flex items-center gap-2 text-slate-500 hover:text-cyan-400 transition-colors uppercase tracking-widest text-xs font-semibold">
         <ArrowLeft className="w-4 h-4" /> Back to History
      </Link>

      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
         <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-3">
              {String(backtest.config_snapshot?.asset_symbol || backtest.config_snapshot?.symbol || "Strategy Result")}
              <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs px-2 py-0.5 rounded-full uppercase tracking-widest">
                {stats.total_return_pct >= 0 ? "Profitable" : "Loss"}
              </span>
            </h1>
            <p className="text-slate-400 text-sm mt-1 uppercase tracking-wider">
               Execution Completed
            </p>
         </div>
      </div>

      {/* Main Chart Area */}
      <div className="glass-card p-4 h-[400px] border-slate-800/50 relative">
         <div className="absolute top-4 left-4 z-10 bg-slate-950/80 backdrop-blur-md px-3 py-1.5 rounded-full border border-slate-800 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Equity Curve</span>
         </div>
         {backtest.results.equity_curve.length > 0 ? (
           <EquityChart
              data={backtest.results.equity_curve.map((ec: { timestamp?: number; equity?: number } | number, idx: number) => ({
                  time: typeof ec === 'object' && ec !== null && 'timestamp' in ec && ec.timestamp ? new Date(ec.timestamp).toISOString() : new Date(startMs + idx * msPerCandle).toISOString(),
                  value: typeof ec === 'object' && ec !== null && 'equity' in ec && ec.equity !== undefined ? Number(ec.equity) : Number(ec)
              }))}
           />
         ) : (
           <div className="w-full h-full flex flex-col items-center justify-center text-slate-600">
              <Activity className="w-8 h-8 mb-2" />
              <p>No equity curve data available</p>
           </div>
         )}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
         {metrics.map((m) => (
           <div key={m.label} className="glass-card p-4 border-slate-800/50 flex flex-col items-center justify-center text-center hover:border-cyan-400/30 transition-colors">
              <m.icon className="w-5 h-5 text-cyan-400 mb-2 opacity-50" />
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-1">{m.label}</p>
              <p className="text-lg font-bold text-slate-100">{m.value}</p>
           </div>
         ))}
      </div>
    </div>
  );
}
