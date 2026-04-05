"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { TopNav } from "@/components/TopNav";
import { fetchApi, BacktestRequest } from "@/lib/api";

const AVAILABLE_PATTERNS = [
  "Double Bottom", "Double Top", "Head and Shoulders", "Inverse H&S", "Triple Bottom",
  "Triple Top", "Rounding Bottom", "Ascending Triangle", "Descending Triangle", "Symmetrical Triangle",
  "Bull Flag", "Bear Flag", "Falling Wedge", "Rising Wedge", "Bullish Pennant",
  "Bearish Pennant", "Cup and Handle", "Inverse C&H", "Bullish Rectangle", "Bearish Rectangle",
  "Three White Soldiers", "Three Black Crows", "Morning Star", "Evening Star"
];

export default function BuilderPage() {
  const router = useRouter();
  
  // Strategy Form State
  const [strategyName, setStrategyName] = useState("");
  const [symbols, setSymbols] = useState(["BTC/USD"]);
  const [timeframe, setTimeframe] = useState("1Hour");
  const [entryPatterns, setEntryPatterns] = useState<string[]>([]);
  const [confluenceMode, setConfluenceMode] = useState<"AND" | "OR">("OR");
  const [rsiPeriod, setRsiPeriod] = useState<number | "">("");
  const [rsiOversold, setRsiOversold] = useState(30);
  const [rsiOverbought, setRsiOverbought] = useState(70);
  const [emaPeriod, setEmaPeriod] = useState<number | "">("");
  const [slippage, setSlippage] = useState(0.001);
  const [fees, setFees] = useState(0.001);
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const togglePattern = (pattern: string) => {
    if (entryPatterns.includes(pattern)) {
      setEntryPatterns(entryPatterns.filter(p => p !== pattern));
    } else {
      setEntryPatterns([...entryPatterns, pattern]);
    }
  };

  const handleRunBacktest = async () => {
    if (entryPatterns.length === 0) {
      setError("Please select at least one entry pattern.");
      return;
    }
    
    // Filter out empty symbols and enforce max 3
    const filteredSymbols = symbols.filter(s => s.trim() !== "").slice(0, 3);
    if (filteredSymbols.length === 0) {
      setError("Please provide at least one asset symbol.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const request: BacktestRequest = {
      strategy_name: strategyName || "Unnamed Strategy",
      symbols: filteredSymbols,
      asset_class: "crypto",
      timeframe,
      entry_patterns: entryPatterns,
      exit_patterns: [], // Simplified for UI
      confluence_mode: confluenceMode,
      slippage,
      fees,
      rsi_period: rsiPeriod === "" ? null : Number(rsiPeriod),
      rsi_oversold: Number(rsiOversold),
      rsi_overbought: Number(rsiOverbought),
      ema_period: emaPeriod === "" ? null : Number(emaPeriod),
    };

    try {
      // In a real app we would get the response and maybe an ID,
      // then redirect to the results page for that specific simulation.
      const result = await fetchApi<any>("/backtest", {
        method: "POST",
        body: JSON.stringify(request),
      });
      
      // For MVP, just route to a dummy results page since we don't have persistence set up perfectly
      // to retrieve specific results by ID yet without another router endpoint.
      router.push("/results?id=latest");
    } catch (e: any) {
      setError(e.message || "Failed to run backtest");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-background text-on-surface font-body selection:bg-primary/30 min-h-screen">
      <TopNav />
      <div className="flex pt-[60px]">
        <Sidebar />
        
        <main className="flex-1 md:ml-64 p-8 min-h-[calc(100vh-60px)] grid grid-cols-1 lg:grid-cols-12 gap-8 tonal-shift">
          {/* Builder Canvas (Left) */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            <header>
              <h1 className="text-4xl font-headline font-black tracking-tighter text-on-surface uppercase drop-shadow-[0_0_15px_rgba(0,242,255,0.2)]">
                Strategy Builder
              </h1>
              <p className="text-on-surface-variant text-xs mt-2 uppercase tracking-widest">
                 Define rules. Set constraints. Deploy simulations.
              </p>
            </header>
            
            {error && (
              <div className="bg-error/10 border border-error text-error p-3 rounded text-sm mb-4">
                {error}
              </div>
            )}

            <div className="glass-panel p-8 rounded-xl border border-outline-variant/10">
              <div className="mb-8">
                <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold mb-2 block">
                  Strategy Name
                </label>
                <input 
                  type="text" 
                  value={strategyName}
                  onChange={(e) => setStrategyName(e.target.value)}
                  className="bg-transparent border-b border-outline-variant/30 w-full pb-2 text-2xl font-headline text-primary focus:outline-none focus:border-primary placeholder:text-outline-variant transition-colors" 
                  placeholder="e.g. Midnight Phoenix v2"
                />
              </div>

              <div className="grid grid-cols-2 gap-6 mb-8">
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold mb-2 block">
                    Assets (Max 3)
                  </label>
                  <input 
                    type="text" 
                    value={symbols.join(", ")}
                    onChange={(e) => setSymbols(e.target.value.split(",").map(s => s.trim()))}
                    className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none text-on-surface"
                    placeholder="BTC/USD, ETH/USD"
                  />
                </div>
                <div>
                   <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold mb-2 block">
                    Timeframe
                  </label>
                  <select 
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                    className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg p-3 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none text-on-surface appearance-none"
                  >
                    <option value="1Min">1 Minute</option>
                    <option value="15Min">15 Minutes</option>
                    <option value="1Hour">1 Hour</option>
                    <option value="4Hour">4 Hours</option>
                    <option value="1Day">1 Day</option>
                  </select>
                </div>
              </div>

              <div className="mb-8">
                 <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface mb-4 pb-2 border-b border-outline-variant/10">
                    Pattern Recognition
                 </h3>
                 <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                    {AVAILABLE_PATTERNS.map((pattern) => {
                      const isSelected = entryPatterns.includes(pattern);
                      return (
                        <div 
                          key={pattern}
                          onClick={() => togglePattern(pattern)}
                          className={`p-3 border rounded-lg cursor-pointer transition-all ${
                            isSelected 
                              ? "bg-primary/10 border-primary text-primary" 
                              : "bg-surface-container-low border-outline-variant/10 hover:border-primary/50 text-on-surface-variant"
                          }`}
                        >
                           <div className="text-xs font-semibold">{pattern}</div>
                        </div>
                      )
                    })}
                 </div>
              </div>

              <div>
                 <div className="flex justify-between items-center mb-4 pb-2 border-b border-outline-variant/10">
                   <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface">
                      Indicator Confluence
                   </h3>
                   <div className="flex bg-surface-container-high rounded p-1">
                      <button 
                        onClick={() => setConfluenceMode("OR")}
                        className={`text-[10px] px-3 py-1 rounded font-bold transition-all ${confluenceMode === "OR" ? "bg-primary text-on-primary" : "text-on-surface-variant"}`}
                      >OR</button>
                      <button 
                        onClick={() => setConfluenceMode("AND")}
                        className={`text-[10px] px-3 py-1 rounded font-bold transition-all ${confluenceMode === "AND" ? "bg-primary text-on-primary" : "text-on-surface-variant"}`}
                      >AND</button>
                   </div>
                 </div>

                 <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* RSI */}
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <label className="text-xs font-bold text-on-surface">RSI Filter (Period)</label>
                        <input 
                          type="number" 
                          value={rsiPeriod}
                          onChange={(e) => setRsiPeriod(e.target.value === "" ? "" : Number(e.target.value))}
                          placeholder="None"
                          className="w-20 bg-surface-container border border-outline-variant/30 rounded text-xs p-1 text-right"
                        />
                      </div>
                      
                      {typeof rsiPeriod === "number" && (
                        <div className="pt-2 border-t border-outline-variant/10 space-y-3">
                          <div>
                            <div className="flex justify-between text-[10px] text-on-surface-variant mb-1">
                              <span>Oversold Entry</span>
                              <span>{rsiOversold}</span>
                            </div>
                            <input 
                              type="range" min="0" max="50" step="1" 
                              value={rsiOversold} onChange={(e) => setRsiOversold(Number(e.target.value))}
                              className="w-full accent-primary" 
                            />
                          </div>
                          <div>
                            <div className="flex justify-between text-[10px] text-on-surface-variant mb-1">
                              <span>Overbought Exit</span>
                              <span>{rsiOverbought}</span>
                            </div>
                            <input 
                              type="range" min="50" max="100" step="1" 
                              value={rsiOverbought} onChange={(e) => setRsiOverbought(Number(e.target.value))}
                              className="w-full accent-error" 
                            />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* EMA */}
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <label className="text-xs font-bold text-on-surface">Cross EMA (Period)</label>
                        <input 
                          type="number" 
                          value={emaPeriod}
                          onChange={(e) => setEmaPeriod(e.target.value === "" ? "" : Number(e.target.value))}
                          placeholder="None"
                          className="w-20 bg-surface-container border border-outline-variant/30 rounded text-xs p-1 text-right"
                        />
                      </div>
                      {typeof emaPeriod === "number" && (
                        <p className="text-[10px] text-on-surface-variant">
                          Entries require price to be above EMA {emaPeriod}. Exits require price to be below EMA {emaPeriod}.
                        </p>
                      )}
                    </div>
                 </div>
              </div>
            </div>
          </div>

          {/* Setup Rules & Action Panel (Right) */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="glass-panel p-6 rounded-xl border border-outline-variant/10 sticky top-[100px]">
               <h3 className="text-sm font-headline font-bold uppercase tracking-widest mb-6">Simulation Guardrails</h3>
               
               <div className="space-y-6 mb-8">
                  <div>
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
                       <span>Slippage %</span>
                       <span className="text-on-surface">{(slippage * 100).toFixed(2)}%</span>
                    </div>
                    <input 
                      type="range" min="0" max="0.05" step="0.001" 
                      value={slippage} onChange={(e) => setSlippage(Number(e.target.value))}
                      className="w-full accent-primary" 
                    />
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
                       <span>Trading Fees %</span>
                       <span className="text-on-surface">{(fees * 100).toFixed(2)}%</span>
                    </div>
                    <input 
                      type="range" min="0" max="0.05" step="0.001" 
                      value={fees} onChange={(e) => setFees(Number(e.target.value))}
                      className="w-full accent-primary" 
                    />
                  </div>
               </div>

               <div className="p-4 rounded-lg bg-primary/5 border border-primary/20 mb-8">
                 <div className="flex gap-2">
                   <span className="material-symbols-outlined text-primary text-sm">info</span>
                   <p className="text-[10px] text-on-surface-variant leading-relaxed">
                     The Obsidian Core strictly applies a 15-minute market safety buffer to real-time inputs. Order routing will be delayed proportionally in live integration.
                   </p>
                 </div>
               </div>

               <button 
                  onClick={handleRunBacktest}
                  disabled={isSubmitting}
                  className="w-full py-4 rounded-xl bg-primary text-on-primary font-headline font-black uppercase tracking-widest shadow-[0_0_20px_rgba(153,247,255,0.3)] hover:shadow-[0_0_30px_rgba(153,247,255,0.5)] transition-all flex justify-center items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
               >
                  {isSubmitting ? (
                    <>
                      <span className="material-symbols-outlined animate-spin">refresh</span>
                      Simulating...
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined">play_arrow</span>
                      Run Simulation
                    </>
                  )}
               </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
