"use client";

import { ArrowLeft, TrendingUp, TrendingDown, Percent, DollarSign, Activity, ShieldCheck, Zap, Info } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { EquityChart } from "@/components/EquityChart";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { getBacktestsByIdOptions } from "@/lib/api/@tanstack/react-query.gen";
import { BacktestRequest } from "@/lib/api/types.gen";
import { formatWinRatePercent, normalizeFidelityScore } from "@/lib/metrics";

export default function BacktestResultsPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: backtest, isLoading } = useQuery(
    getBacktestsByIdOptions({
      path: { id }
    })
  );

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <span className="w-8 h-8 border-2 border-slate-800 border-t-cyan-400 rounded-full animate-spin" />
        <p className="text-white text-sm animate-pulse tracking-widest uppercase font-bold">Synchronizing Physics...</p>
      </div>
    );
  }

  if (!backtest) return <div className="text-center py-20 text-slate-400 uppercase tracking-widest font-bold">Forge Entry Not Found</div>;

  const stats = backtest.results;
  const config = backtest.config_snapshot as BacktestRequest & { capital?: number };
  const capital = config.capital || 100000;

  const metrics = [
    { label: "Net Return", value: `${(stats.total_return_pct ?? 0).toFixed(2)}%`, icon: Percent, color: "text-emerald-400" },
    { label: "Absolute Profit", value: `$${(((stats.total_return_pct ?? 0) / 100) * capital).toLocaleString()}`, icon: DollarSign, color: "text-slate-100" },
    { label: "Fidelity Score", value: `${Math.round(normalizeFidelityScore(stats.reality_gap_metrics?.fidelity_score) * 100)}%`, icon: ShieldCheck, color: "text-cyan-400" },
    { label: "Win Rate", value: formatWinRatePercent(stats.win_rate), icon: TrendingUp, color: "text-slate-100" },
    { label: "Max Drawdown", value: `${(stats.max_drawdown_pct ?? 0).toFixed(2)}%`, icon: TrendingDown, color: "text-red-400" },
    { label: "Sharpe Ratio", value: (stats.sharpe_ratio ?? 0).toFixed(2), icon: Activity, color: "text-purple-400" },
  ];

  const chartSeries = [
    {
      label: "Execution Forge (Realistic)",
      data: (stats.equity_curve || []).map((v: number, i: number) => ({
        time: new Date(Date.now() - (100 - i) * 86400000).toISOString(),
        value: typeof v === 'object' ? (v as { equity?: number; value?: number }).equity || (v as { equity?: number; value?: number }).value || 0 : v
      })),
      color: "#00f0ff",
      type: "area" as const
    },
    {
      label: `Benchmark (${stats.benchmark_symbol || "SPY"})`,
      data: (stats.benchmark_equity_curve || []).map((v: number, i: number) => ({
        time: new Date(Date.now() - (100 - i) * 86400000).toISOString(),
        value: typeof v === 'object' ? (v as { equity?: number; value?: number }).equity || (v as { equity?: number; value?: number }).value || 0 : v
      })),
      color: "#94a3b8",
      type: "line" as const,
      lineWidth: 1
    }
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-32">
      <Link href="/history" className="inline-flex items-center gap-2 text-slate-500 hover:text-cyan-400 transition-all uppercase tracking-tighter text-[10px] font-bold">
         <ArrowLeft className="w-3 h-3" /> System History / Forge Logs
      </Link>

      {/* Fidelity Audit Header */}
      <div className="flex flex-col md:flex-row items-end justify-between gap-6 bg-slate-950/40 p-8 rounded-3xl border border-slate-800/50 relative overflow-hidden">
         <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 blur-[100px] rounded-full -translate-y-1/2 translate-x-1/2" />

         <div className="relative z-10">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-[0.3em]">Simulation Audit</span>
              <div className="h-px w-12 bg-slate-800" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-100 mb-1">
              {String(config.symbols?.[0] || "Strategy")} <span className="text-slate-700 font-light">vs</span> {String(stats.benchmark_symbol || "Benchmark")}
            </h1>
            <p className="text-slate-500 text-xs font-mono uppercase tracking-widest">
              Execution Physics: Institutional (POV {(config.participation_rate ?? 0) * 100}% | VA-Sens {config.va_sensitivity || 1.0}x)
            </p>
         </div>

         <div className="flex items-center gap-8 relative z-10">
            <div className="text-right">
              <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-1">Fidelity Grade</p>
              <div className="flex items-center gap-3">
                <span className={cn("text-3xl font-black font-mono", normalizeFidelityScore(stats.reality_gap_metrics?.fidelity_score) > 0.9 ? "text-cyan-400" : "text-amber-400")}>
                   {Math.round(normalizeFidelityScore(stats.reality_gap_metrics?.fidelity_score) * 100)}%
                 </span>
                 <div className="w-12 h-1.5 bg-slate-900 rounded-full overflow-hidden">
                   <div className="h-full bg-cyan-400" style={{ width: `${normalizeFidelityScore(stats.reality_gap_metrics?.fidelity_score) * 100}%` }} />
                 </div>
              </div>
            </div>
            <div className="w-px h-10 bg-slate-800" />
            <div className="px-6 py-3 rounded-2xl bg-cyan-500 text-slate-950 font-bold text-sm tracking-tight shadow-lg shadow-cyan-500/20">
              Pass Fidelity Audit
            </div>
         </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Metric Grid */}
        <div className="lg:col-span-1 grid grid-cols-1 gap-4">
           {metrics.map((m) => (
             <div key={m.label} className="glass-card p-5 border-slate-800/40 flex flex-col justify-between hover:border-slate-700 transition-all group">
                <div className="flex justify-between items-start">
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">{m.label}</p>
                  <m.icon className="w-3.5 h-3.5 text-slate-700 group-hover:text-cyan-400/50 transition-colors" />
                </div>
                <p className={cn("text-2xl font-bold mt-2 font-mono", m.color)}>{m.value}</p>
             </div>
           ))}
        </div>

        {/* The Duel Canvas */}
        <div className="lg:col-span-3 glass-card p-6 border-slate-800 relative min-h-[450px]">
           <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#00f0ff]" />
                  <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">Strategy</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-slate-500" />
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{stats.benchmark_symbol || "Benchmark"}</span>
                </div>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-950 border border-slate-800 rounded-lg">
                <Zap size={10} className="text-amber-500" />
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">Dual-Pass Sim</span>
              </div>
           </div>

           <div className="h-[350px]">
             <EquityChart series={chartSeries} />
           </div>
        </div>
      </div>

      {/* The Reality Gap - Attribution Audit */}
      <div className="glass-card p-8 border-slate-800/50">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-400/20 flex items-center justify-center">
            <Info className="text-orange-400 w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-slate-100">The Reality Gap</h3>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">Drag Decomposition & Institutional Friction Audit</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
           <div className="space-y-4">
              <div className="flex justify-between items-end">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-tight">Slippage Drag</p>
                <p className="text-lg font-bold text-orange-400 font-mono">-{((stats.reality_gap_metrics?.slippage_impact_pct ?? 0) * 10000).toFixed(1)} <span className="text-[10px]">BPS</span></p>
              </div>
              <div className="h-1 w-full bg-slate-900 rounded-full overflow-hidden">
                <div className="h-full bg-orange-400" style={{ width: `${Math.min((stats.reality_gap_metrics?.slippage_impact_pct ?? 0) * 1000, 100)}%` }} />
              </div>
              <p className="text-[10px] text-slate-600 italic">Realistic latency & VA-Slippage execution impact.</p>
           </div>

           <div className="space-y-4">
              <div className="flex justify-between items-end">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-tight">Fee Attrition</p>
                <p className="text-lg font-bold text-red-400 font-mono">-{((stats.reality_gap_metrics?.fee_impact_pct ?? 0) * 100).toFixed(2)}%</p>
              </div>
              <div className="h-1 w-full bg-slate-900 rounded-full overflow-hidden">
                <div className="h-full bg-red-400" style={{ width: `${Math.min((stats.reality_gap_metrics?.fee_impact_pct ?? 0) * 1000, 100)}%` }} />
              </div>
              <p className="text-[10px] text-slate-600 italic">Cumulative impact of exchange & broker commissions.</p>
           </div>

           <div className="space-y-4">
              <div className="flex justify-between items-end">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-tight">Vol Hazard</p>
                <p className="text-lg font-bold text-amber-500 font-mono">-{((stats.reality_gap_metrics?.vol_hazard_pct ?? 0) * 100).toFixed(2)}%</p>
              </div>
              <div className="h-1 w-full bg-slate-900 rounded-full overflow-hidden">
                <div className="h-full bg-amber-500" style={{ width: `${Math.min((stats.reality_gap_metrics?.vol_hazard_pct ?? 0) * 1000, 100)}%` }} />
              </div>
              <p className="text-[10px] text-slate-600 italic">Execution difficulty during ATR standard deviation spikes.</p>
           </div>
        </div>
      </div>
    </div>
  );
}
