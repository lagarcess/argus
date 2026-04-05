"use client";

import { Sidebar } from "@/components/Sidebar";
import { TopNav } from "@/components/TopNav";

export default function HistoryPage() {
  return (
    <div className="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen">
      <TopNav />
      <div className="flex pt-[60px]">
        <Sidebar />

        <main className="flex-1 md:ml-64 p-8 min-h-[calc(100vh-60px)] tonal-shift">
          <header className="mb-12">
            <h1 className="text-5xl font-black font-headline tracking-tighter text-on-surface mb-2">History</h1>
            <p className="text-on-surface-variant text-sm max-w-2xl">
              Browse your complete log of simulated executions. Data integrity is maintained via the Obsidian core.
            </p>
          </header>

          {/* Filters & Stats Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-12">
            <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-2xl relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl rounded-full"></div>
              <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">
                Total Executions
              </span>
              <div className="text-4xl font-black font-headline text-on-surface">1,248</div>
            </div>

            <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-2xl">
              <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">
                Success Rate
              </span>
              <div className="text-4xl font-black font-headline text-secondary">64.2%</div>
            </div>

            <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-2xl">
              <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">
                Avg. Return
              </span>
              <div className="text-4xl font-black font-headline text-primary">+12.4%</div>
            </div>

            <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-2xl flex items-center justify-between">
              <div>
                <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">
                  Filter Log
                </span>
                <div className="flex gap-2">
                  <span className="material-symbols-outlined text-primary cursor-pointer">filter_list</span>
                  <span className="material-symbols-outlined text-on-surface-variant cursor-pointer">search</span>
                </div>
              </div>
              <button className="bg-surface-container-highest px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-widest hover:text-primary transition-colors">
                Export CSV
              </button>
            </div>
          </div>

          {/* Backtest Table */}
          <div className="bg-surface-container-low rounded-xl shadow-2xl border border-outline-variant/10 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[800px]">
                <thead>
                  <tr className="bg-surface-container-high/50 text-[10px] uppercase tracking-[0.2em] text-on-surface-variant font-bold">
                    <th className="px-8 py-5 border-b border-outline-variant/10">Strategy Name</th>
                    <th className="px-8 py-5 border-b border-outline-variant/10">Execution Date</th>
                    <th className="px-8 py-5 border-b border-outline-variant/10">Return %</th>
                    <th className="px-8 py-5 border-b border-outline-variant/10">Status</th>
                    <th className="px-8 py-5 border-b border-outline-variant/10 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-outline-variant/5">
                  <tr className="hover:bg-primary/5 transition-colors group">
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="font-bold text-on-surface tracking-tight">Vortex-Alpha_v4.2</span>
                        <span className="text-[10px] text-neutral-500 uppercase tracking-widest mt-1">ETH/USDT 4H Range</span>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-on-surface-variant text-xs">Oct 24, 2026</td>
                    <td className="px-8 py-6">
                      <span className="bg-secondary-container/20 text-secondary px-3 py-1 rounded-full text-xs font-bold border border-secondary/20">
                        +24.52%
                      </span>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-secondary shadow-[0_0_10px_#2ff801]"></div>
                        <span className="text-[10px] uppercase tracking-widest font-bold">Completed (Sim)</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex items-center justify-end gap-4">
                        <button className="text-primary hover:text-primary-dim text-xs font-bold uppercase tracking-widest transition-colors">View Results</button>
                        <button className="text-on-surface-variant hover:text-on-surface transition-colors">
                          <span className="material-symbols-outlined text-sm">edit</span>
                        </button>
                        <button className="text-on-surface-variant hover:text-error transition-colors">
                          <span className="material-symbols-outlined text-sm">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>

                  {/* Mock Pending Row */}
                  <tr className="hover:bg-primary/5 transition-colors group">
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="font-bold text-on-surface tracking-tight">Neural-Scalper-Prime</span>
                        <span className="text-[10px] text-neutral-500 uppercase tracking-widest mt-1">SOL/USDT 1m Noise</span>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-on-surface-variant text-xs">Oct 21, 2026</td>
                    <td className="px-8 py-6">
                      <span className="bg-secondary-container/20 text-secondary px-3 py-1 rounded-full text-xs font-bold border border-secondary/20">
                        --
                      </span>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-tertiary animate-pulse shadow-[0_0_10px_#ac89ff]"></div>
                        <span className="text-[10px] uppercase tracking-widest font-bold text-tertiary">Processing</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex items-center justify-end gap-4 opacity-50">
                        <button className="text-neutral-600 text-xs font-bold uppercase tracking-widest cursor-not-allowed">Wait...</button>
                        <button className="text-on-surface-variant"><span className="material-symbols-outlined text-sm">edit</span></button>
                        <button className="text-on-surface-variant"><span className="material-symbols-outlined text-sm">delete</span></button>
                      </div>
                    </td>
                  </tr>

                  {/* Mock Failed Row */}
                  <tr className="hover:bg-primary/5 transition-colors group">
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="font-bold text-on-surface tracking-tight">Arbitrage-Bot-Beta</span>
                        <span className="text-[10px] text-neutral-500 uppercase tracking-widest mt-1">Cross-Exchange Synth</span>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-on-surface-variant text-xs">Oct 19, 2026</td>
                    <td className="px-8 py-6">
                      <span className="bg-surface-variant text-on-surface-variant px-3 py-1 rounded-full text-xs font-bold border border-outline-variant/20">
                        0.00%
                      </span>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-error shadow-[0_0_10px_#ff716c]"></div>
                        <span className="text-[10px] uppercase tracking-widest font-bold">Failed</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex items-center justify-end gap-4">
                        <button className="text-primary hover:text-primary-dim text-xs font-bold uppercase tracking-widest transition-colors">Logs</button>
                        <button className="text-on-surface-variant hover:text-on-surface transition-colors">
                          <span className="material-symbols-outlined text-sm">edit</span>
                        </button>
                        <button className="text-on-surface-variant hover:text-error transition-colors">
                          <span className="material-symbols-outlined text-sm">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="px-8 py-4 bg-surface-container-high/30 flex justify-between items-center text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">
              <span>Showing 1-14 of 1,248 entries</span>
              <div className="flex gap-4">
                <button className="hover:text-primary transition-colors">Previous</button>
                <span className="text-primary">1</span>
                <button className="hover:text-primary transition-colors">2</button>
                <button className="hover:text-primary transition-colors">3</button>
                <span>...</span>
                <button className="hover:text-primary transition-colors">Next</button>
              </div>
            </div>
          </div>

          <footer className="w-full mt-12 py-8 flex flex-col md:flex-row justify-between items-center opacity-50 text-[10px] tracking-wider uppercase border-t border-outline-variant/10">
            <div className="mb-4 md:mb-0">
              © 2026 ARGUS QUANTITATIVE. REALITY GAP APPLIED.
            </div>
            <div className="text-error font-bold">
              DISCLAIMER: SIMULATION ONLY. NO REAL ASSETS INVOLVED.
            </div>
          </footer>
        </main>
      </div>

      {/* Mobile nav placeholder */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full h-16 bg-[#0e0e10]/80 backdrop-blur-xl border-t border-neutral-800/20 flex justify-around items-center z-50">
        <span className="material-symbols-outlined text-neutral-500">grid_view</span>
        <span className="material-symbols-outlined text-neutral-500">add_box</span>
        <span className="material-symbols-outlined text-cyan-400" style={{ fontVariationSettings: "'FILL' 1" }}>history</span>
        <span className="material-symbols-outlined text-neutral-500">account_circle</span>
      </nav>
    </div>
  );
}
