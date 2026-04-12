"use client";

import { useQuery } from "@tanstack/react-query";
import { Copy, Trash2, ArrowRight, Clock } from "lucide-react";
import Link from "next/link";
// In real app, import from lib/api
import { getStrategiesOptions } from "@/lib/api/@tanstack/react-query.gen";

type StrategyListItem = {
  id: string;
  name: string;
  timeframe: string;
  is_executed: boolean;
  created_at: string;
};

export default function StrategiesPage() {
  const { data: strategies, isLoading } = useQuery(getStrategiesOptions());
  // const { data: strategies, isLoading } = useQuery({
    // queryKey
    // queryFn
  // });

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-slate-900 border border-emerald-400/30 flex items-center justify-center">
            <Copy className="text-emerald-400 w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">Saved Strategies</h1>
            <p className="text-slate-400 text-sm">Manage and execute your saved trading ideas.</p>
          </div>
        </div>
        <Link href="/builder" className="btn-primary text-sm shadow-none! py-1.5 px-4 hidden sm:block">
          + New Strategy
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {isLoading ? (
           <div className="col-span-full h-40 flex flex-col items-center justify-center text-slate-500">
             <div className="relative w-12 h-12 flex items-center justify-center">
               <div className="absolute inset-0 rounded-full border-t-2 border-cyan-400/20 blur-sm animate-[spin_3s_linear_infinite]" />
               <div className="absolute inset-2 rounded-full border-r-2 border-emerald-400/40 blur-[1px] animate-[spin_2s_ease-in-out_infinite_reverse]" />
               <div className="w-2 h-2 bg-slate-100 rounded-full shadow-[0_0_10px_#fff]" />
             </div>
             <p className="text-[10px] uppercase tracking-widest text-slate-500 mt-4 animate-pulse">Loading Strategies...</p>
           </div>
        ) : strategies?.data?.length === 0 ? (
           <div className="col-span-full py-20 text-center glass-card border-slate-800 border-dashed flex flex-col items-center justify-center">
             <Copy className="w-8 h-8 text-slate-600 mb-4" />
             <h3 className="text-lg font-semibold text-slate-300">No Strategies Found</h3>
             <p className="text-slate-500 text-sm mt-1 mb-6">Design your first trading strategy without writing code.</p>
             <Link href="/builder" className="btn-secondary text-sm">Create Strategy</Link>
           </div>
        ) : (
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          strategies?.data?.map((strat: StrategyListItem | any) => (
            <div key={strat.id} className="glass-card p-5 border-slate-800 hover:border-emerald-400/30 transition-colors flex flex-col justify-between group h-40">
               <div>
                  <div className="flex items-start justify-between mb-2">
                     <h3 className="font-bold text-slate-100 truncate pr-4">{strat.name}</h3>
                     {/* Per api_contract.md: Only delete if NOT executed */}
                     <button className="text-slate-600 hover:text-red-400 transition-colors shrink-0">
                        <Trash2 className="w-4 h-4" />
                     </button>
                  </div>
                  <div className="flex gap-2">
                     <span className="bg-slate-900 border border-slate-700 text-slate-400 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full font-semibold">
                       {strat.timeframe}
                     </span>
                     <span className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full font-semibold">
                       {strat.is_executed ? "Executed" : "Draft"}
                     </span>
                  </div>
               </div>

               <div className="flex items-center justify-between border-t border-slate-800/50 pt-4 mt-4">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                     <Clock className="w-3 h-3" />
                     {new Date(strat.created_at).toLocaleDateString()}
                  </div>
                  <Link href={`/builder?id=${strat.id}`} className="text-emerald-400 text-xs font-semibold uppercase tracking-wider flex items-center gap-1 group-hover:text-emerald-300">
                     Edit <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-1" />
                  </Link>
               </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
