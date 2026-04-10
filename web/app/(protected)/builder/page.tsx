"use client";

import { useForm } from "react-hook-form";
import { Plus, Play, Save, Trash2, Activity } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
// In real app, import from lib/api
import { mockRunBacktest } from "@/lib/mockApi";
import type { BacktestRequest } from "@/lib/api";
import { toast } from "sonner";
import { showErrorToast } from "@/components/ErrorToast";
import { cn } from "@/lib/utils";
import { checkProfanity } from "glin-profanity";
import { Controller } from "react-hook-form";

const MAJOR_ASSETS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK.B", "BTC/USD", "ETH/USD"];
const AVAILABLE_INDICATORS = ["SMA", "EMA", "RSI", "MACD", "ATR", "Bollinger Bands", "VWAP", "Stochastic"];

// Matching Pydantic StrategyCreate
type StrategyCreate = {
  name: string;
  asset_symbol: string;
  timeframe: "1Min" | "5Min" | "15Min" | "1H" | "1D";
  period_start: string;
  period_end: string;
  parameters: Record<string, number | boolean>; // Using generic dict for indicators
  entry_criteria: Array<{
    indicator_a: string;
    operator: "gt" | "lt" | "cross_above" | "cross_below" | "eq";
    indicator_b?: string;
    value?: number;
  }>;
  exit_criteria: Array<{
    indicator_a: string;
    operator: "gt" | "lt" | "cross_above" | "cross_below" | "eq";
    indicator_b?: string;
    value?: number;
  }>;
  slippage_bps: number;
  fees_per_trade_bps: number;
  capital: number;
  trade_direction: "LONG" | "SHORT" | "BOTH";
};

const OPERATORS = [
  { value: "gt", label: "is greater than" },
  { value: "lt", label: "is less than" },
  { value: "cross_above", label: "crosses above" },
  { value: "cross_below", label: "crosses below" },
  { value: "eq", label: "is equal to" },
];

function CurrencyInput({ control, name, label, error }: { control: any; name: string; label: string; error?: { message?: string } }) {
  const MAX_CAPITAL = 100000000;

  const format = (val: number | string) => {
    if (val === undefined || val === null || val === "" || val === 0) return "";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(Number(val));
  };

  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase flex justify-between">
        {label}
        {error && <span className="text-red-400 text-[10px]">{error.message}</span>}
      </label>
      <Controller
        name={name}
        control={control}
        rules={{
          required: "Required",
          min: { value: 100, message: "Min $100" },
          max: { value: MAX_CAPITAL, message: "Max $100M" }
        }}
        render={({ field: { onChange, value } }) => {
          const displayValue = format(value);

          return (
            <input
              type="text"
              value={displayValue}
              onChange={(e) => {
                const raw = e.target.value.replace(/[^0-9.]/g, "");
                let num = parseFloat(raw);
                if (isNaN(num)) num = 0;

                // Enforce hard cap
                if (num > MAX_CAPITAL) num = MAX_CAPITAL;

                onChange(num);
              }}
              className={cn(
                "w-full bg-slate-950 border rounded-lg px-4 py-2 text-slate-100 font-mono focus:outline-none focus:ring-1",
                error ? "border-red-500/50 focus:border-red-400 focus:ring-red-400/50" : "border-slate-800 focus:border-emerald-400 focus:ring-emerald-400/50"
              )}
              placeholder="$100,000"
            />
          );
        }}
      />
    </div>
  );
}

type CriteriaItem = StrategyCreate['entry_criteria'][number];

function CriteriaBuilder({
  label,
  items,
  onAdd,
  onRemove,
  onChange,
  indicators
}: {
  label: string;
  items: CriteriaItem[];
  onAdd: () => void;
  onRemove: (idx: number) => void;
  onChange: (idx: number, field: keyof CriteriaItem, value: string | number | undefined) => void;
  indicators: string[];
}) {
  const canAddRule = items.length < 1 || process.env.NEXT_PUBLIC_FEATURE_MULTI_RULES === "true";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800/50 pb-2">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">{label}</h3>
        {canAddRule && (
          <button
            type="button"
            onClick={onAdd}
            className="text-[10px] font-bold text-cyan-400 hover:text-cyan-300 uppercase tracking-widest flex items-center gap-1"
          >
            <Plus size={10} /> Add Rule
          </button>
        )}
      </div>

      <div className="space-y-3">
        {items.map((item, idx) => {
          const indA = item.indicator_a.split('_')[0] || "SMA";
          const paramA = item.indicator_a.split('_')[1] || "10";
          const isBIndicator = !!item.indicator_b;
          const indB = isBIndicator ? (item.indicator_b!.split('_')[0] || "SMA") : "";
          const paramB = isBIndicator ? (item.indicator_b!.split('_')[1] || "10") : "";

          return (
            <div key={`${idx}-${item.indicator_a}`} className="flex flex-col sm:flex-row items-center gap-2 bg-slate-900/30 p-3 rounded-xl border border-slate-800/50 group animate-in slide-in-from-left-2 duration-300">
              <div className="w-full sm:flex-1 grid grid-cols-1 sm:grid-cols-[1fr_min-content_1fr] gap-2 items-center">

                {/* Indicator A */}
                <div className="flex bg-slate-950 border border-slate-800 rounded-lg overflow-hidden focus-within:border-cyan-400">
                  <select
                    value={indA}
                    onChange={(e) => onChange(idx, "indicator_a", `${e.target.value}_${paramA}`)}
                    className="w-full bg-transparent px-2 py-1.5 text-xs text-slate-200 focus:outline-none"
                  >
                    {indicators.map(i => <option key={`a-${i}`} value={i}>{i}</option>)}
                  </select>
                  <input
                    type="number"
                    value={paramA}
                    onChange={(e) => onChange(idx, "indicator_a", `${indA}_${e.target.value}`)}
                    className="w-16 border-l border-slate-800 bg-slate-900/50 px-2 py-1.5 text-xs text-slate-400 text-center focus:outline-none focus:text-cyan-400"
                  />
                </div>

                {/* Operator */}
                <select
                  value={item.operator}
                  onChange={(e) => onChange(idx, "operator", e.target.value as CriteriaItem['operator'])}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-center text-cyan-400 font-bold focus:outline-none focus:border-cyan-400 min-w-32"
                >
                  {OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                </select>

                {/* Target (Indicator B or Value) */}
                <div className="flex gap-2">
                  <select
                    value={item.indicator_b ? "indicator" : "value"}
                    onChange={(e) => {
                      if (e.target.value === "value") {
                        onChange(idx, "indicator_b", undefined);
                        onChange(idx, "value", 50);
                      } else {
                        const nextInd = indicators.filter(i => i !== indA)[0] || "RSI";
                        onChange(idx, "indicator_b", `${nextInd}_14`);
                        onChange(idx, "value", undefined);
                      }
                    }}
                    className="w-32 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-400 shrink-0"
                  >
                    <option value="value">Constant Value</option>
                    <option value="indicator">Indicator</option>
                  </select>

                  {item.indicator_b ? (
                    <div className="flex flex-1 bg-slate-950 border border-slate-800 rounded-lg overflow-hidden focus-within:border-cyan-400">
                      <select
                        value={indB}
                        onChange={(e) => onChange(idx, "indicator_b", `${e.target.value}_${paramB}`)}
                        className="w-full bg-transparent px-2 py-1.5 text-xs text-slate-200 focus:outline-none"
                      >
                        {indicators.map(i => <option key={`b-${i}`} value={i}>{i}</option>)}
                      </select>
                      <input
                        type="number"
                        value={paramB}
                        onChange={(e) => onChange(idx, "indicator_b", `${indB}_${e.target.value}`)}
                        className="w-16 border-l border-slate-800 bg-slate-900/50 px-2 py-1.5 text-xs text-slate-400 text-center focus:outline-none focus:text-cyan-400"
                      />
                    </div>
                  ) : (
                    <input
                      type="number"
                      value={item.value !== undefined ? item.value : 50}
                      onChange={(e) => onChange(idx, "value", parseFloat(e.target.value))}
                      className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-400"
                      placeholder="50"
                    />
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onRemove(idx)}
                className="p-2 text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 shrink-0"
              >
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
        {items.length === 0 && (
          <div className="py-8 text-center border border-dashed border-slate-800 rounded-2xl">
            <p className="text-[10px] text-slate-600 uppercase tracking-widest font-bold">No active rules defined</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function BuilderPage() {
  const router = useRouter();
  const [showRealityGap, setShowRealityGap] = useState(false);
  const [showRules, setShowRules] = useState(true);

  const form = useForm<StrategyCreate>({
    defaultValues: {
      name: "",
      asset_symbol: "AAPL",
      timeframe: "1H",
      period_start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      period_end: new Date().toISOString().split('T')[0],
      parameters: { sma_fast: 10, sma_slow: 30 },
      entry_criteria: [
        { indicator_a: "SMA_10", operator: "cross_above", indicator_b: "SMA_30" }
      ],
      exit_criteria: [
        { indicator_a: "RSI_14", operator: "gt", value: 70 }
      ],
      slippage_bps: 1.5,
      fees_per_trade_bps: 0.5,
      capital: 100000,
      trade_direction: "LONG"
    }
  });

  const { isPending, mutateAsync } = useMutation({
    mutationFn: mockRunBacktest, // Uses mock backend
    onSuccess: (data) => {
      toast.success("Backtest Completed", {
        className: "bg-emerald-950 border-emerald-500/50 text-emerald-100"
      });
      router.push(`/backtest/${data.id}`);
    },
    onError: showErrorToast
  });

  const onSubmit = async (data: StrategyCreate, isDraft: boolean) => {
    if (isDraft) {
      toast.success("Draft saved successfully");
      router.push("/strategies");
      // TODO: Implement save draft API call.
      return;
    }

    // Validation for Backtest
    if (data.entry_criteria.length === 0 || data.exit_criteria.length === 0) {
      toast.error("Set Entry and Exit Rules", {
        description: "You need at least one rule for each to run a backtest.",
        className: "bg-red-950 border-red-500/50 text-red-100"
      });
      return;
    }

    // Execute backtest immediately
    await mutateAsync(data as unknown as BacktestRequest);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-slate-900 border border-cyan-400/30 flex items-center justify-center">
          <Plus className="text-cyan-400 w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Design Your Strategy</h1>
          <p className="text-slate-400 text-sm">Create and simulate trading setups without writing code.</p>
        </div>
      </div>

      <form className="space-y-6">

        {/* Core Strategy Configuration */}
        <section className="glass-card p-6 space-y-6 border-slate-800/50">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500 border-b border-slate-800/50 pb-2">
            Core Configuration
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase flex justify-between">
                Strategy Name
                {form.formState.errors.name && <span className="text-red-400 text-[10px]">{form.formState.errors.name.message}</span>}
              </label>
              <input
                {...form.register("name", {
                  required: "Required",
                  validate: (v) => !checkProfanity(v).containsProfanity || "Please use appropriate language."
                })}
                className={cn(
                  "w-full bg-slate-950 border rounded-lg px-4 py-2 text-slate-100 focus:outline-none focus:ring-1",
                  form.formState.errors.name ? "border-red-500/50 focus:border-red-400 focus:ring-red-400/50" : "border-slate-800 focus:border-cyan-400 focus:ring-cyan-400/50"
                )}
                placeholder="e.g. SMA Crossover"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase flex justify-between">
                Asset Symbol
                {form.formState.errors.asset_symbol && <span className="text-red-400 text-[10px]">{form.formState.errors.asset_symbol.message}</span>}
              </label>
              <input
                list="asset-suggestions"
                {...form.register("asset_symbol", {
                  required: "Required",
                  validate: (v) => MAJOR_ASSETS.includes(v.toUpperCase()) || "Unsupported asset. Select from list."
                })}
                className={cn(
                  "w-full bg-slate-950 border rounded-lg px-4 py-2 uppercase text-slate-100 focus:outline-none focus:ring-1",
                  form.formState.errors.asset_symbol ? "border-red-500/50 focus:border-red-400 focus:ring-red-400/50" : "border-slate-800 focus:border-cyan-400 focus:ring-cyan-400/50"
                )}
                placeholder="AAPL"
              />
              <datalist id="asset-suggestions">
                {MAJOR_ASSETS.map((asset) => (
                  <option key={asset} value={asset} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Timeframe</label>
              <select {...form.register("timeframe")} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-slate-100 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 appearance-none">
                <option value="1Min">1 Minute</option>
                <option value="5Min">5 Minutes</option>
                <option value="15Min">15 Minutes</option>
                <option value="1H">1 Hour</option>
                <option value="1D">1 Day</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Start Date</label>
              <input type="date" {...form.register("period_start")} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-slate-400 focus:text-slate-100 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">End Date</label>
              <input type="date" {...form.register("period_end")} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-slate-400 focus:text-slate-100 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50" />
            </div>
          </div>
        </section>

        <section className="glass-card p-6 border-slate-800/50">
          {/* Rules Unified Shell */}
          <div
            className={cn("flex items-center justify-between cursor-pointer select-none", showRules ? "border-b border-slate-800/50 pb-4 mb-4" : "")}
            onClick={() => setShowRules(!showRules)}
          >
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-100 flex items-center gap-2">
                <Activity size={16} className="text-cyan-400" />
                Rules
              </h2>
              <p className="text-xs text-slate-500 mt-1">Add technical indicator to your entry and exit triggers.</p>
            </div>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center bg-slate-950 border border-slate-800 transition-transform ${showRules ? 'rotate-180' : ''}`}>
              <Plus className="w-4 h-4 text-slate-400" />
            </div>
          </div>

          <AnimatePresence>
            {showRules && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden space-y-8"
              >
                {/* Indicator Chips Integration */}
                <div className="pt-2">
                  <div className="flex flex-wrap gap-2">
                    {AVAILABLE_INDICATORS.map(ind => {
                      const isActive = form.watch("parameters")[ind.toLowerCase()] !== undefined ||
                        form.watch("entry_criteria").some(c => c.indicator_a.includes(ind) || c.indicator_b?.includes(ind)) ||
                        form.watch("exit_criteria").some(c => c.indicator_a.includes(ind) || c.indicator_b?.includes(ind));

                      return (
                        <button
                          type="button"
                          key={ind}
                          className={cn(
                            "px-3 py-1.5 rounded-full border text-xs font-medium transition-all duration-300",
                            isActive
                              ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.2)]"
                              : "border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300"
                          )}
                          onClick={() => {
                            const current = form.getValues("parameters");
                            if (current[ind.toLowerCase()]) {
                              const next = { ...current };
                              delete next[ind.toLowerCase()];
                              form.setValue("parameters", next);
                            } else {
                              form.setValue("parameters", { ...current, [ind.toLowerCase()]: true });
                            }
                          }}
                        >
                          {isActive ? "✓" : "+"} {ind}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-8 border-t border-slate-800/50 pt-6">
                  <CriteriaBuilder
                    label="Entry Conditions"
                    items={form.watch("entry_criteria")}
                    indicators={AVAILABLE_INDICATORS}
                    onAdd={() => {
                      const current = form.getValues("entry_criteria");
                      form.setValue("entry_criteria", [...current, { indicator_a: "SMA", operator: "gt", value: 50 }]);
                    }}
                    onRemove={(idx) => {
                      const current = form.getValues("entry_criteria");
                      form.setValue("entry_criteria", current.filter((_, i) => i !== idx));
                    }}
                    onChange={(idx, field, value) => {
                      const current = [...form.getValues("entry_criteria")];
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      (current[idx] as any)[field] = value;
                      form.setValue("entry_criteria", current);
                    }}
                  />

                  <CriteriaBuilder
                    label="Exit Conditions"
                    items={form.watch("exit_criteria")}
                    indicators={AVAILABLE_INDICATORS}
                    onAdd={() => {
                      const current = form.getValues("exit_criteria");
                      form.setValue("exit_criteria", [...current, { indicator_a: "RSI", operator: "lt", value: 30 }]);
                    }}
                    onRemove={(idx) => {
                      const current = form.getValues("exit_criteria");
                      form.setValue("exit_criteria", current.filter((_, i) => i !== idx));
                    }}
                    onChange={(idx, field, value) => {
                      const current = [...form.getValues("exit_criteria")];
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      (current[idx] as any)[field] = value;
                      form.setValue("exit_criteria", current);
                    }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Reality Gap Expandable */}
        <section className="glass-card p-6 border-slate-800/50 mt-6">
          <div
            className={cn("flex items-center justify-between cursor-pointer select-none", showRealityGap ? "border-b border-slate-800/50 pb-4 mb-4" : "")}
            onClick={() => setShowRealityGap(!showRealityGap)}
          >
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-100 flex items-center gap-2">
                Reality Gap Setup
                <span className="bg-emerald-500/10 text-emerald-400 text-[10px] px-2 py-0.5 rounded-full border border-emerald-400/20">Crucial</span>
              </h2>
              <p className="text-xs text-slate-500 mt-1">Configure trading friction and constraints.</p>
            </div>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center bg-slate-950 border border-slate-800 transition-transform ${showRealityGap ? 'rotate-180' : ''}`}>
              <Plus className="w-4 h-4 text-slate-400" />
            </div>
          </div>

          <AnimatePresence>
            {showRealityGap && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                  <CurrencyInput
                    control={form.control}
                    name="capital"
                    label="Initial Capital"
                    error={form.formState.errors.capital}
                  />
                  <div className="space-y-2">
                    <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Trade Direction</label>
                    <select {...form.register("trade_direction")} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-slate-100 focus:outline-none focus:border-emerald-400 appearance-none">
                      <option value="LONG">Long Only</option>
                      <option value="SHORT">Short Only</option>
                      {process.env.NEXT_PUBLIC_FEATURE_BOTH_DIRECTION === "true" && (
                        <option value="BOTH">Both (Long & Short)</option>
                      )}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Slippage (bps)</label>
                    <input type="number" step="0.1" {...form.register("slippage_bps", { valueAsNumber: true })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-slate-100 focus:outline-none focus:border-emerald-400" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Fees/Trade (bps)</label>
                    <input type="number" step="0.1" {...form.register("fees_per_trade_bps", { valueAsNumber: true })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-slate-100 focus:outline-none focus:border-emerald-400" />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Global Action Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-end gap-4 pt-6 border-t border-slate-800/50">
          <button
            type="button"
            onClick={form.handleSubmit((d) => onSubmit(d, true))}
            disabled={isPending}
            className="w-full sm:w-auto btn-secondary flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" /> Save Draft
          </button>
          <button
            type="button"
            onClick={form.handleSubmit((d) => onSubmit(d, false))}
            disabled={isPending}
            className="w-full sm:w-auto btn-primary flex items-center justify-center gap-2"
          >
            {isPending ? (
              <span className="w-5 h-5 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
            ) : (
              <><Play className="w-4 h-4 fill-current" /> Backtest</>
            )}
          </button>
        </div>

      </form>
    </div>
  );
}
