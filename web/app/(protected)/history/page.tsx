"use client";

import { useQuery } from "@tanstack/react-query";
import { History as HistoryIcon, ArrowRight, Activity } from "lucide-react";
import Link from "next/link";
// In real app, import from lib/api
import { mockGetHistory } from "@/lib/mockApi";

export type SimulationLogEntry = {
  id: string;
  strategy_name?: string;
  symbols: string[];
  timeframe: string;
  total_return_pct: number;
  created_at: string;
  period_start?: string;
  period_end?: string;
};

export default function HistoryPage() {
  const { data: backtests, isLoading } = useQuery({
    queryKey: ['backtests'],
    queryFn: () => mockGetHistory(),
  });

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-20">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-slate-900 border border-cyan-400/30 flex items-center justify-center">
          <HistoryIcon className="text-cyan-400 w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Computation History</h1>
          <p className="text-slate-400 text-sm">Review your previously executed execution runs.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {isLoading ? (
           <div className="col-span-full h-40 flex flex-col items-center justify-center text-slate-500">
             <div className="relative w-12 h-12 flex items-center justify-center">
               <div className="absolute inset-0 rounded-full border-t-2 border-cyan-400/20 blur-sm animate-[spin_3s_linear_infinite]" />
               <div className="absolute inset-2 rounded-full border-r-2 border-emerald-400/40 blur-[1px] animate-[spin_2s_ease-in-out_infinite_reverse]" />
               <div className="w-2 h-2 bg-slate-100 rounded-full shadow-[0_0_10px_#fff]" />
             </div>
             <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-4 animate-pulse">Retrieving History...</p>
           </div>
        ) : backtests?.simulations?.length === 0 ? (
           <div className="col-span-full py-20 text-center glass-card border-slate-800 border-dashed flex flex-col items-center justify-center">
             <Activity className="w-8 h-8 text-slate-600 mb-4" />
             <h3 className="text-lg font-semibold text-slate-300">No Backtests Found</h3>
             <p className="text-slate-500 text-sm mt-1 mb-6">You haven't run any strategies yet.</p>
             <Link href="/builder" className="btn-secondary text-sm">Go to Builder</Link>
           </div>
        ) : (
          backtests?.simulations?.map((bt: SimulationLogEntry) => (
            <Link key={bt.id} href={`/backtest/${bt.id}`} className="block">
              <div className="glass-card p-5 border-slate-800 hover:border-cyan-400/50 transition-colors flex flex-col justify-between group h-32 relative overflow-hidden">

                 {/* Decorative Glow */}
                 <div className={`absolute top-0 right-0 w-32 h-32 blur-3xl opacity-10 rounded-full ${
                    bt.total_return_pct >= 0 ? "bg-emerald-500" : "bg-red-500"
                 }`} />

                 <div className="relative z-10 flex items-start justify-between">
                    <div>
                      <h3 className="font-bold text-slate-100 uppercase tracking-widest">{bt.symbols?.[0] || 'UNKNOWN'}</h3>
                      <p className="text-xs text-slate-500 mt-1">
                        {bt.period_start ? new Date(bt.period_start).toLocaleDateString() : new Date(bt.created_at).toLocaleDateString()} - {bt.period_end ? new Date(bt.period_end).toLocaleDateString() : "Now"}
                      </p>
                    </div>
                    <div className={`text-sm font-bold flex items-center gap-1 ${
                      bt.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}>
                       {bt.total_return_pct >= 0 ? "+" : ""}
                       {bt.total_return_pct?.toFixed(2)}%
                    </div>
                 </div>

                 <div className="relative z-10 flex items-center justify-between border-t border-slate-800/50 pt-3 mt-3">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                       {new Date(bt.created_at).toLocaleDateString()}
                    </span>
                    <span className="text-cyan-400 text-xs font-semibold uppercase tracking-wider flex items-center gap-1 group-hover:text-cyan-300">
                       View Report <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-1" />
                    </span>
                 </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
