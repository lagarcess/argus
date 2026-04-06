"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthContext";
import { Sidebar } from "@/components/Sidebar";
import { TopNav } from "@/components/TopNav";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/");
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="bg-background min-h-screen flex items-center justify-center">
        <div className="text-primary font-headline animate-pulse uppercase tracking-widest">Loading Session...</div>
      </div>
    );
  }

  return (
    <div className="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen">
      <TopNav />
      <div className="flex pt-[60px]">
        <Sidebar />

        <main className="flex-1 md:ml-64 p-8 min-h-[calc(100vh-60px)]">
          {/* Header Row */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full bg-secondary shadow-[0_0_10px_rgba(47,248,1,0.5)] animate-pulse"></span>
                <span className="text-[10px] uppercase tracking-[0.2em] font-bold text-secondary">Argus Core Active</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-black font-headline tracking-tighter text-on-surface">Dashboard</h1>
              <p className="text-on-surface-variant font-body text-sm mt-1">Real-time simulation metrics & system health.</p>
            </div>

            <div className="flex gap-4">
              <button className="px-6 py-2 rounded-full border border-outline-variant/30 hover:border-primary/50 text-xs font-bold uppercase tracking-widest transition-colors flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">download</span> Report
              </button>
              <button className="px-6 py-2 rounded-full bg-primary text-on-primary-container text-xs font-bold uppercase tracking-widest shadow-[0_0_15px_rgba(153,247,255,0.2)] hover:shadow-[0_0_25px_rgba(153,247,255,0.4)] transition-all flex items-center gap-2">
                <span className="material-symbols-outlined text-sm">add</span> New Strategy
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Top Cards */}
            <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-lg relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl rounded-full group-hover:bg-primary/10 transition-colors"></div>
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-4">Total Net P&L (Sim)</span>
                <div className="text-4xl font-headline font-black text-secondary">+$14,289.50</div>
                <div className="mt-4 flex items-center gap-2 text-xs">
                  <span className="text-secondary font-bold flex items-center"><span className="material-symbols-outlined text-xs">trending_up</span> 2.4%</span>
                  <span className="text-on-surface-variant">vs last 30 days</span>
                </div>
              </div>

              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-lg">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-4">Active Strategies</span>
                <div className="text-4xl font-headline font-black text-on-surface">12</div>
                <div className="mt-4 flex items-center gap-2 text-xs">
                  <span className="text-on-surface-variant">3 pending manual review</span>
                </div>
              </div>

              <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-lg">
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-4">Compute Credits</span>
                <div className="text-4xl font-headline font-black text-primary">8,450</div>
                <div className="mt-4 w-full bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                  <div className="bg-primary h-full w-[45%]"></div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="lg:col-span-4 bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-lg">
               <h3 className="text-sm font-headline font-bold uppercase tracking-widest text-on-surface-variant mb-6">Quick Actions</h3>
               <div className="space-y-3">
                 <button className="w-full flex justify-between items-center p-4 rounded-lg bg-surface-container-highest border border-outline-variant/10 hover:border-primary/30 transition-colors group">
                   <div className="flex items-center gap-3">
                     <span className="material-symbols-outlined text-primary">psychology</span>
                     <span className="text-xs font-bold uppercase tracking-wide">Run Neural Net Optimizer</span>
                   </div>
                   <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors text-sm">arrow_forward</span>
                 </button>
                 <button className="w-full flex justify-between items-center p-4 rounded-lg bg-surface-container-highest border border-outline-variant/10 hover:border-primary/30 transition-colors group">
                   <div className="flex items-center gap-3">
                     <span className="material-symbols-outlined text-secondary">candlestick_chart</span>
                     <span className="text-xs font-bold uppercase tracking-wide">Historical Sync</span>
                   </div>
                   <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors text-sm">arrow_forward</span>
                 </button>
               </div>
            </div>

            {/* Simulation History Log */}
            <div className="lg:col-span-8 bg-surface-container-low rounded-xl border border-outline-variant/10 shadow-lg overflow-hidden flex flex-col">
              <div className="p-6 border-b border-outline-variant/10 flex justify-between items-center bg-surface-container-high/30">
                <h3 className="text-sm font-headline font-bold uppercase tracking-widest">Simulation History Log</h3>
                <span className="text-[10px] text-primary uppercase tracking-widest font-bold cursor-pointer hover:underline">View All</span>
              </div>
              <div className="overflow-x-auto flex-1">
                <table className="w-full text-left text-sm">
                  <thead className="bg-surface-container-highest text-[10px] uppercase tracking-widest text-on-surface-variant">
                    <tr>
                      <th className="px-6 py-4 font-medium">Strategy</th>
                      <th className="px-6 py-4 font-medium">Symbol</th>
                      <th className="px-6 py-4 font-medium">Action</th>
                      <th className="px-6 py-4 font-medium">Price</th>
                      <th className="px-6 py-4 font-medium text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/5">
                    <tr className="hover:bg-surface-container-highest/50 transition-colors">
                      <td className="px-6 py-4 font-bold text-xs tracking-tight">Alpha-Vortex</td>
                      <td className="px-6 py-4 text-xs font-mono text-on-surface-variant">ETH/USDT</td>
                      <td className="px-6 py-4"><span className="text-secondary text-[10px] font-bold uppercase tracking-widest">Buy Limit</span></td>
                      <td className="px-6 py-4 text-xs font-mono">3,241.50</td>
                      <td className="px-6 py-4 text-right">
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-secondary-container/20 text-secondary border border-secondary/20 text-[10px] font-bold uppercase tracking-widest">
                          Completed (Sim)
                        </span>
                      </td>
                    </tr>
                     <tr className="hover:bg-surface-container-highest/50 transition-colors">
                      <td className="px-6 py-4 font-bold text-xs tracking-tight">Momentum Breakout</td>
                      <td className="px-6 py-4 text-xs font-mono text-on-surface-variant">BTC/USD</td>
                      <td className="px-6 py-4"><span className="text-error text-[10px] font-bold uppercase tracking-widest">Sell Market</span></td>
                      <td className="px-6 py-4 text-xs font-mono">68,412.00</td>
                      <td className="px-6 py-4 text-right">
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-secondary-container/20 text-secondary border border-secondary/20 text-[10px] font-bold uppercase tracking-widest">
                          Completed (Sim)
                        </span>
                      </td>
                    </tr>
                    <tr className="hover:bg-surface-container-highest/50 transition-colors">
                      <td className="px-6 py-4 font-bold text-xs tracking-tight">Mean Reversion Q</td>
                      <td className="px-6 py-4 text-xs font-mono text-on-surface-variant">SOL/USDT</td>
                      <td className="px-6 py-4"><span className="text-secondary text-[10px] font-bold uppercase tracking-widest">Buy Limit</span></td>
                      <td className="px-6 py-4 text-xs font-mono">142.75</td>
                      <td className="px-6 py-4 text-right">
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-surface-variant text-on-surface-variant border border-outline-variant/30 text-[10px] font-bold uppercase tracking-widest">
                          Pending
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* System Resources */}
            <div className="lg:col-span-4 bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-lg">
              <h3 className="text-sm font-headline font-bold uppercase tracking-widest text-on-surface-variant mb-6">Argus Node Diagnostics</h3>

              <div className="space-y-6">
                <div>
                  <div className="flex justify-between text-xs mb-2">
                    <span className="font-mono text-on-surface-variant">Memory Usage</span>
                    <span className="font-mono font-bold text-primary">64%</span>
                  </div>
                  <div className="w-full bg-surface-container-highest rounded-full h-1">
                    <div className="bg-primary h-full w-[64%] shadow-[0_0_10px_#99f7ff]"></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-2">
                    <span className="font-mono text-on-surface-variant">CPU Load (Numba JIT)</span>
                    <span className="font-mono font-bold text-secondary">28%</span>
                  </div>
                  <div className="w-full bg-surface-container-highest rounded-full h-1">
                    <div className="bg-secondary h-full w-[28%] shadow-[0_0_10px_#2ff801]"></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-2">
                    <span className="font-mono text-on-surface-variant">API Rate Limit</span>
                    <span className="font-mono font-bold text-error">89%</span>
                  </div>
                  <div className="w-full bg-surface-container-highest rounded-full h-1">
                    <div className="bg-error h-full w-[89%] shadow-[0_0_10px_#ff716c]"></div>
                  </div>
                  <p className="text-[10px] text-error mt-2 font-mono">Warning: Approaching Alpaca rate limit.</p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
