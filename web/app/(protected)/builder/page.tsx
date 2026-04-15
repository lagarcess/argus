"use client";

import { useForm } from "react-hook-form";
import { Plus, Play, Save, Activity, Search, Clock, Calendar, Info, ChevronDown, X, Zap, Lock } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { postBacktestsMutation, getAuthSessionOptions } from "@/lib/api/@tanstack/react-query.gen";

import { toast } from "sonner";
import { showErrorToast } from "@/components/ErrorToast";
import { cn } from "@/lib/utils";
import { checkProfanity } from "glin-profanity";
import { Controller, Control, Path } from "react-hook-form";

// Core Shell Components
import { CriteriaBuilder } from "@/components/builder/CriteriaBuilder";
import { IndicatorSelector } from "@/components/builder/IndicatorSelector";
import { AssetSelector } from "@/components/builder/AssetSelector";
import { INDICATOR_REGISTRY } from "@/lib/indicators";
import { ASSET_REGISTRY } from "@/lib/assets";

const PINNED_INDICATORS = ["SMA", "RSI", "MACD", "EMA"];

export type StrategyCreate = {
  name: string;
  asset_symbol: string;
  timeframe: "15Min" | "1H" | "2H" | "4H" | "12H" | "1D";
  period_start: string;
  period_end: string;
  parameters: Record<string, number | boolean>;
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
  participation_rate: number;
  execution_priority: number;
  va_sensitivity: number;
  slippage_model: "fixed" | "vol_adjusted";
  stop_loss_pct?: number;
  take_profit_pct?: number;
};

function CurrencyInput({ control, name, label, error }: { control: Control<StrategyCreate>; name: Path<StrategyCreate>; label: string; error?: { message?: string } }) {
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
    <div className="space-y-4">
      <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase flex justify-between h-4 items-center">
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
          const displayValue = format(value as string | number);
          return (
            <input
              type="text"
              value={displayValue}
              onChange={(e) => {
                const raw = e.target.value.replace(/[^0-9.]/g, "");
                let num = parseFloat(raw);
                if (isNaN(num)) num = 0;
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

const formatYMD = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const parseYMD = (s: string) => {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
};

const formatDisplayDate = (s: string) => {
  return parseYMD(s).toLocaleDateString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric'
  });
};

export default function BuilderPage() {
  const router = useRouter();
  const [showRealityGap, setShowRealityGap] = useState(false);
  const [showRules, setShowRules] = useState(true);
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);
  const [isAssetSelectorOpen, setIsAssetSelectorOpen] = useState(false);
  const [isTimeframeOpen, setIsTimeframeOpen] = useState(false);
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);
  const [recentIndicator, setRecentIndicator] = useState<string | null>(null);
  const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);
  const [datePickerTarget, setDatePickerTarget] = useState<'start' | 'end'>('start');
  const [calendarView, setCalendarView] = useState(new Date());

  const [lastFocusedSlot, setLastFocusedSlot] = useState<{
    type: 'entry' | 'exit';
    index: number;
    field: 'indicator_a' | 'indicator_b';
  }>({ type: 'entry', index: 0, field: 'indicator_a' });

  const { data: sessionData } = useQuery(getAuthSessionOptions());
  const tier = sessionData?.subscription_tier || 'free';
  const today = new Date();

  const form = useForm<StrategyCreate>({
    defaultValues: {
      name: "",
      asset_symbol: "AAPL",
      timeframe: "1H",
      period_start: formatYMD(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 30)),
      period_end: formatYMD(today),
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
      trade_direction: "LONG",
      participation_rate: 0.1,
      execution_priority: 1.0,
      va_sensitivity: 1.0,
      slippage_model: "vol_adjusted"
    }
  });

  const timeframe = form.watch("timeframe");

  const getMinDate = () => {
    // If we're still loading the session, allow full access to avoid flickering lockout
    if (!sessionData) return new Date(2016, 0, 1);

    const isIntraday = timeframe !== "1D";
    if (tier === 'max') return new Date(2016, 0, 1);
    if (tier === 'pro') return new Date(today.getFullYear() - 5, today.getMonth(), today.getDate());
    if (tier === 'plus') return new Date(today.getFullYear() - 3, today.getMonth(), today.getDate());

    // Free / Basic
    if (isIntraday) return new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());
    return new Date(today.getFullYear() - 5, today.getMonth(), today.getDate());
  };

  const minDate = getMinDate();
  const maxDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  const { isPending, mutateAsync } = useMutation({
    ...postBacktestsMutation(),
    onSuccess: (data) => {
      toast.success("Backtest Completed", {
        className: "bg-emerald-950 border-emerald-500/50 text-emerald-100"
      });
      router.push(`/backtest/${data.id}`);
    },
    onError: showErrorToast
  });

  const handleIndicatorSelect = (indicatorId: string) => {
    const { type, index, field } = lastFocusedSlot;
    const path = type === 'entry' ? 'entry_criteria' : 'exit_criteria';
    const currentRules = [...form.getValues(path)];
    const rule = { ...currentRules[index] };

    // Check Institutional Physics (physics guard)
    const entryRules = form.getValues("entry_criteria");
    const exitRules = form.getValues("exit_criteria");
    const allUsed = [
      ...entryRules.map(r => r.indicator_a.split('_')[0]),
      ...entryRules.map(r => r.indicator_b?.split('_')[0]).filter(Boolean),
      ...exitRules.map(r => r.indicator_a.split('_')[0]),
      ...exitRules.map(r => r.indicator_b?.split('_')[0]).filter(Boolean),
    ];

    // Is this a NEW indicator or just re-assigning?
    const currentIndicatorId = field === 'indicator_a' ? rule.indicator_a.split('_')[0] : rule.indicator_b?.split('_')[0];
    const isNew = !allUsed.includes(indicatorId) && indicatorId !== currentIndicatorId;
    const uniqueCount = new Set(allUsed).size;

    if (isNew && uniqueCount >= 4) {
      toast.error("Institutional Limit Reached", {
        description: "Execution Forge physics only support 4 concurrent technical indicators across all rules.",
        className: "bg-slate-950 border-slate-800 text-slate-200"
      });
      return;
    }

    const registryItem = INDICATOR_REGISTRY.find(i => i.id === indicatorId);
    const period = registryItem?.defaultPeriod || 10;

    if (field === 'indicator_a') {
      rule.indicator_a = `${indicatorId}_${period}`;
    } else {
      rule.indicator_b = `${indicatorId}_${period}`;
      rule.value = undefined;
    }

    currentRules[index] = rule;
    form.setValue(path, currentRules);

    // Update Recent Slot logic
    if (!PINNED_INDICATORS.includes(indicatorId)) {
      setRecentIndicator(indicatorId);
    }

    setIsSelectorOpen(false);

    toast.success(`Assigned ${indicatorId} to ${type === 'entry' ? 'Entry' : 'Exit'} Rule ${index + 1}`, {
      className: cn(
        "border-none shadow-2xl",
        type === 'entry' ? "bg-blue-600 text-white" : "bg-rose-600 text-white"
      )
    });
  };

  const onSubmit = async (data: StrategyCreate, isDraft: boolean) => {
    if (isDraft) {
      toast.success("Draft saved successfully");
      router.push("/strategies");
      return;
    }

    const allRules = [...data.entry_criteria, ...data.exit_criteria];
    const hasGhost = allRules.some(r => !r.indicator_a || r.indicator_a.trim() === "" || (r.indicator_b === ""));

    if (hasGhost) {
      toast.error("Complete Your Rules", {
        description: "Some rules are missing indicators. Please select an indicator for all pulsing slots.",
        className: "bg-amber-950 border-amber-500/50 text-amber-100"
      });
      return;
    }

    if (data.entry_criteria.length === 0 || data.exit_criteria.length === 0) {
      toast.error("Set Entry and Exit Rules", {
        description: "You need at least one rule for each to run a backtest.",
        className: "bg-red-950 border-red-500/50 text-red-100"
      });
      return;
    }

    // Map to API BacktestRequest
    const apiPayload = {
      name: data.name,
      symbols: [data.asset_symbol],
      timeframe: data.timeframe,
      start_date: new Date(data.period_start).toISOString(),
      end_date: new Date(data.period_end).toISOString(),
      entry_criteria: data.entry_criteria,
      exit_criteria: data.exit_criteria,
      slippage: data.slippage_bps / 10000,
      fees: data.fees_per_trade_bps / 10000,
      participation_rate: data.participation_rate,
      execution_priority: data.execution_priority,
      va_sensitivity: data.va_sensitivity,
      slippage_model: data.slippage_model,
      stop_loss_pct: data.stop_loss_pct,
      take_profit_pct: data.take_profit_pct,
    };

    await mutateAsync({ body: apiPayload as Parameters<typeof mutateAsync>[0]['body'] });
  };

  const generateCalendarDays = () => {
    const year = calendarView.getFullYear();
    const month = calendarView.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const days = [];
    for (let i = 0; i < firstDay; i++) days.push(null);
    for (let i = 1; i <= daysInMonth; i++) days.push(new Date(year, month, i));
    return days;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20 px-4 sm:px-0">
      <div className="flex flex-col gap-1 mb-10 mt-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-400/20 flex items-center justify-center">
            <Activity className="text-cyan-400 w-4 h-4" />
          </div>
          <h1 className="text-lg font-bold uppercase tracking-[0.3em] text-slate-100">The Recipe Forge</h1>
        </div>
        <p className="text-slate-500 text-[10px] uppercase tracking-widest pl-11">Design and calibrate your market execution logic</p>
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
              <div
                onClick={() => setIsAssetSelectorOpen(true)}
                className={cn(
                  "w-full bg-slate-950 border rounded-lg px-4 py-2 flex items-center justify-between cursor-pointer group transition-all",
                  form.formState.errors.asset_symbol ? "border-red-500/50" : "border-slate-800 hover:border-slate-700"
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="text-slate-100 font-bold uppercase tracking-widest">{form.watch("asset_symbol")}</span>
                  <span className="text-[10px] text-slate-500 font-medium">
                    {ASSET_REGISTRY.find(a => a.symbol === form.watch("asset_symbol"))?.name || "Select Asset"}
                  </span>
                </div>
                <Search size={14} className="text-slate-600 group-hover:text-cyan-400 transition-colors" />
              </div>
              <input type="hidden" {...form.register("asset_symbol", { required: "Required" })} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Timeframe</label>
              <div
                onClick={() => setIsTimeframeOpen(true)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 flex items-center justify-between cursor-pointer group hover:border-slate-700 transition-all"
              >
                <div className="flex items-center gap-2">
                  <Clock size={14} className="text-slate-500 group-hover:text-cyan-400" />
                  <span className="text-sm text-slate-100 font-bold uppercase tracking-widest">{form.watch("timeframe")}</span>
                </div>
                <ChevronDown size={14} className="text-slate-600" />
              </div>
              <input type="hidden" {...form.register("timeframe")} />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Start Date</label>
              <div
                onClick={() => {
                  setDatePickerTarget('start');
                  setCalendarView(new Date(form.getValues('period_start')));
                  setIsDatePickerOpen(true);
                }}
                className="relative group cursor-pointer"
              >
                <div className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 pl-10 pr-4 flex items-center justify-between hover:border-cyan-400 transition-all">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-hover:text-cyan-400 transition-colors" size={14} />
                  <span className="text-sm text-slate-100 font-mono tracking-widest uppercase">
                    {formatDisplayDate(form.watch("period_start"))}
                  </span>
                </div>
              </div>
              <input type="hidden" {...form.register("period_start")} />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">End Date</label>
              <div
                onClick={() => {
                  setDatePickerTarget('end');
                  setCalendarView(new Date(form.getValues('period_end')));
                  setIsDatePickerOpen(true);
                }}
                className="relative group cursor-pointer"
              >
                <div className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2 pl-10 pr-4 flex items-center justify-between hover:border-cyan-400 transition-all">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-hover:text-cyan-400 transition-colors" size={14} />
                  <span className="text-sm text-slate-100 font-mono tracking-widest uppercase">
                    {formatDisplayDate(form.watch("period_end"))}
                  </span>
                </div>
              </div>
              <input type="hidden" {...form.register("period_end")} />
            </div>
          </div>
        </section>

        <section className="glass-card p-6 border-slate-800/50">
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
                {/* Indicator Filter/Browse Shell */}
                <div className="pt-2">
                  <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                    {[...PINNED_INDICATORS, ...(recentIndicator ? [recentIndicator] : [])].map(ind => {
                      const entryCriteria = form.watch("entry_criteria") || [];
                      const exitCriteria = form.watch("exit_criteria") || [];
                      const usedInEntry = entryCriteria.some(c => c.indicator_a.startsWith(ind) || c.indicator_b?.startsWith(ind));
                      const usedInExit = exitCriteria.some(c => c.indicator_a.startsWith(ind) || c.indicator_b?.startsWith(ind));
                      const isActive = usedInEntry || usedInExit;

                      return (
                        <button
                          type="button"
                          key={ind}
                          className={cn(
                            "px-3 py-1.5 rounded-full border text-[10px] font-bold uppercase tracking-wider transition-all duration-300 relative overflow-hidden group/pill",
                            isActive
                              ? (usedInEntry && usedInExit)
                                ? "border-indigo-500/50 bg-indigo-500/10 text-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.2)]"
                                : usedInEntry
                                  ? "border-blue-500/50 bg-blue-500/10 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]"
                                  : "border-rose-500/50 bg-rose-500/10 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)]"
                              : "border-slate-800 bg-slate-950 hover:border-slate-700 text-slate-500 hover:text-slate-300"
                          )}
                          onClick={() => handleIndicatorSelect(ind)}
                        >
                          <span className="relative z-10">{ind}</span>
                          {!isActive && (
                             <Plus size={8} className="inline-block ml-1 opacity-50 group-hover/pill:opacity-100 transition-opacity" />
                          )}
                        </button>
                      );
                    })}

                    <button
                      type="button"
                      onClick={() => setIsSelectorOpen(true)}
                      className="px-3 py-1.5 rounded-full border border-slate-700 bg-slate-900/50 hover:bg-slate-800 text-slate-400 hover:text-slate-100 text-xs font-bold transition-all flex items-center gap-2 group"
                    >
                      <Plus size={10} className="group-hover:rotate-90 transition-transform" />
                      Browse All...
                    </button>
                  </div>
                </div>

                <div className="space-y-8 border-t border-slate-800/50 pt-6">
                  <CriteriaBuilder
                    label="Entry Conditions"
                    type="entry"
                    items={form.watch("entry_criteria")}
                    onFocus={(idx, field) => setLastFocusedSlot({ type: 'entry', index: idx, field })}
                    onOpenSelector={() => setIsSelectorOpen(true)}
                    onAdd={() => {
                      const current = form.getValues("entry_criteria");
                      form.setValue("entry_criteria", [...current, { indicator_a: "", operator: "gt", value: 50 }]);
                      setLastFocusedSlot({ type: 'entry', index: current.length, field: 'indicator_a' });
                    }}
                    onRemove={(idx) => {
                      const current = form.getValues("entry_criteria");
                      form.setValue("entry_criteria", current.filter((_, i) => i !== idx));
                    }}
                    onChange={(idx, field, value) => {
                      const current = [...form.getValues("entry_criteria")];
                      current[idx] = { ...current[idx], [field]: value };
                      form.setValue("entry_criteria", current);
                    }}
                  />

                  <CriteriaBuilder
                    label="Exit Conditions"
                    type="exit"
                    items={form.watch("exit_criteria")}
                    onFocus={(idx, field) => setLastFocusedSlot({ type: 'exit', index: idx, field })}
                    onOpenSelector={() => setIsSelectorOpen(true)}
                    onAdd={() => {
                      const current = form.getValues("exit_criteria");
                      form.setValue("exit_criteria", [...current, { indicator_a: "", operator: "lt", value: 30 }]);
                      setLastFocusedSlot({ type: 'exit', index: current.length, field: 'indicator_a' });
                    }}
                    onRemove={(idx) => {
                      const current = form.getValues("exit_criteria");
                      form.setValue("exit_criteria", current.filter((_, i) => i !== idx));
                    }}
                    onChange={(idx, field, value) => {
                      const current = [...form.getValues("exit_criteria")];
                      current[idx] = { ...current[idx], [field]: value };
                      form.setValue("exit_criteria", current);
                    }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Execution Forge (Institutional Physics) */}
        <section className="glass-card p-6 border-slate-800/50 mt-6 relative overflow-hidden group/forge">
          <div className="flex items-center justify-between border-b border-slate-800/50 pb-4 mb-6">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-100">
                Execution Forge
              </h2>
              {tier === 'free' && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-500/30 text-[8px] font-bold text-amber-500 uppercase tracking-tighter">
                  <Lock size={8} /> Pro
                </span>
              )}
            </div>
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center bg-slate-950 border border-slate-800 transition-transform cursor-pointer hover:border-slate-600 ${showRealityGap ? 'rotate-180' : ''}`}
              onClick={() => setShowRealityGap(!showRealityGap)}
            >
              <Plus className="w-4 h-4 text-slate-400" />
            </div>
          </div>

          <AnimatePresence>
            {showRealityGap && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden space-y-8 relative"
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4 items-start">
                  <div
                    className="space-y-4 relative group"
                    onMouseEnter={() => setActiveTooltip("participation")}
                    onMouseLeave={() => setActiveTooltip(null)}
                  >
                    <div className="flex justify-between items-end">
                      <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Participation (POV)</label>
                      <span className="text-cyan-400 font-mono text-sm">{(form.watch("participation_rate") * 100).toFixed(0)}%</span>
                    </div>
                    <input
                      type="range"
                      min="0.01"
                      max="0.5"
                      step="0.01"
                      disabled={tier === 'free'}
                      {...form.register("participation_rate", { valueAsNumber: true })}
                      className={cn(
                        "w-full h-1.5 bg-slate-900 rounded-lg appearance-none transition-all",
                        tier !== 'free' ? "accent-cyan-400 cursor-pointer" : "accent-slate-700 cursor-not-allowed grayscale opacity-30"
                      )}
                    />
                    <AnimatePresence>
                      {activeTooltip === "participation" && (
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.95 }}
                          className="absolute z-50 bottom-full left-0 mb-4 p-4 glass-card border-slate-700 w-80 shadow-2xl"
                        >
                          <div className="flex items-start gap-3">
                            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
                              <Info size={16} />
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-slate-100 mb-1">Participation of Volume (POV)</p>
                              <p className="text-[10px] leading-relaxed text-slate-400">
                                Limits trade size to a % of bar volume. Lower rates simulate higher liquidity constraints (institutional realism).
                              </p>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  <div
                    className="space-y-4 relative group"
                    onMouseEnter={() => setActiveTooltip("aggressiveness")}
                    onMouseLeave={() => setActiveTooltip(null)}
                  >
                    <div className="flex justify-between items-end">
                      <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Agressiveness</label>
                      <span className={cn(
                        "text-[10px] font-mono px-2 py-0.5 rounded border uppercase tracking-tighter",
                        form.watch("execution_priority") > 0.7 ? "text-orange-400 border-orange-400/20 bg-orange-400/5" :
                        form.watch("execution_priority") > 0.3 ? "text-amber-400 border-amber-400/20 bg-amber-400/5" :
                        "text-emerald-400 border-emerald-400/20 bg-emerald-400/5"
                      )}>
                         {form.watch("execution_priority") > 0.7 ? "Aggressive (Taker)" :
                          form.watch("execution_priority") > 0.3 ? "Balanced" : "Passive (Maker)"}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      disabled={tier === 'free'}
                      {...form.register("execution_priority", { valueAsNumber: true })}
                      className={cn(
                        "w-full h-1.5 bg-slate-900 rounded-lg appearance-none transition-all",
                        tier !== 'free' ? "accent-amber-500 cursor-pointer" : "accent-slate-700 cursor-not-allowed grayscale opacity-30"
                      )}
                    />
                    <AnimatePresence>
                      {activeTooltip === "aggressiveness" && (
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.95 }}
                          className="absolute z-50 bottom-full right-0 mb-4 p-4 glass-card border-slate-700 w-80 shadow-2xl"
                        >
                          <div className="flex items-start gap-3">
                            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-500">
                              <Zap size={16} />
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-slate-100 mb-1">Execution Priority</p>
                              <p className="text-[10px] leading-relaxed text-slate-400">
                                <span className="text-orange-400 font-bold">Aggressive</span>: Costs full spread for instant fills.<br/>
                                <span className="text-emerald-400 font-bold">Passive</span>: Captures spread savings but faces higher adverse selection risk.
                              </p>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
                  <div className="space-y-4">
                    <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Cost Physics</label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        disabled={tier === 'free'}
                        onClick={() => form.setValue("slippage_model", "fixed")}
                        className={cn(
                          "px-4 py-3 rounded-xl border text-[10px] font-bold tracking-[0.2em] uppercase transition-all",
                          form.watch("slippage_model") === "fixed"
                            ? "bg-slate-100 border-slate-100 text-slate-950 shadow-xl"
                            : "bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700",
                          tier === 'free' && "opacity-30 grayscale cursor-not-allowed"
                        )}
                      >
                        Fixed Drag
                      </button>
                      <button
                        type="button"
                        disabled={tier === 'free'}
                        onClick={() => form.setValue("slippage_model", "vol_adjusted")}
                        className={cn(
                          "px-4 py-3 rounded-xl border text-[10px] font-bold tracking-[0.2em] uppercase transition-all",
                          form.watch("slippage_model") === "vol_adjusted"
                            ? "bg-cyan-500 border-cyan-500 text-white shadow-xl shadow-cyan-500/20"
                            : "bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700",
                          tier === 'free' && "opacity-30 grayscale cursor-not-allowed"
                        )}
                      >
                        Vol Adjusted
                      </button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-between items-end">
                      <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase">Impact Sensitivity</label>
                      <span className={cn("font-mono text-sm", tier !== 'free' ? "text-pink-500" : "text-slate-500")}>
                        {form.watch("va_sensitivity")}x
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0.5"
                      max="3"
                      step="0.1"
                      disabled={tier === 'free'}
                      {...form.register("va_sensitivity", { valueAsNumber: true })}
                      className={cn(
                        "w-full h-1.5 bg-slate-900 rounded-lg appearance-none transition-all",
                        tier !== 'free' ? "accent-pink-500 cursor-pointer" : "accent-slate-700 cursor-not-allowed grayscale opacity-30"
                      )}
                    />
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-800/50">
                  <CurrencyInput
                    control={form.control}
                    name="capital"
                    label="Initial Capital"
                    error={form.formState.errors.capital}
                  />
                </div>

                {/* Premium Lock Overlay */}
                {mounted && tier === 'free' && (
                  <div className="absolute inset-x-0 bottom-0 top-[60px] bg-slate-950/60 backdrop-blur-[2px] z-20 flex flex-col items-center justify-center p-8 text-center border-t border-white/5 shadow-2xl rounded-b-xl">
                    <div className="w-14 h-14 rounded-3xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center mb-5 shadow-2xl shadow-orange-500/20 animate-pulse">
                      <Lock className="text-white w-7 h-7" />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-2 tracking-tight group-hover/forge:scale-105 transition-transform duration-300">
                      Execution Forge
                    </h3>
                    <p className="text-[10px] text-slate-400 max-w-[320px] mb-8 leading-relaxed font-medium">
                      Unlock high-fidelity institutional physics including <span className="text-cyan-400">POV Gating</span>, <span className="text-amber-400">Maker/Taker Priority</span>, and <span className="text-pink-400">Vol-Adjusted Cost Physics</span>.
                    </p>
                    <button
                      type="button"
                      onClick={() => router.push('/pricing')}
                      className="px-8 py-3 bg-white text-slate-950 rounded-full text-[11px] font-black tracking-[0.25em] uppercase hover:bg-emerald-400 hover:shadow-[0_0_30px_rgba(52,211,153,0.3)] transition-all flex items-center gap-3 group/cta transform active:scale-95"
                    >
                      Upgrade to Pro
                      <Zap size={14} className="fill-current group-hover/cta:translate-x-1 transition-transform" />
                    </button>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Action Bar */}
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

      <IndicatorSelector
        isOpen={isSelectorOpen}
        type={lastFocusedSlot.type}
        onClose={() => setIsSelectorOpen(false)}
        onSelect={handleIndicatorSelect}
      />

      <AssetSelector
        isOpen={isAssetSelectorOpen}
        onClose={() => setIsAssetSelectorOpen(false)}
        onSelect={(symbol) => {
          form.setValue("asset_symbol", symbol);
          setIsAssetSelectorOpen(false);
          toast.success(`Market Selected: ${symbol}`, {
            className: "bg-slate-950 border-cyan-500/50 text-cyan-400"
          });
        }}
      />

      <AnimatePresence>
        {isDatePickerOpen && (
          <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/60 backdrop-blur-md p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden"
            >
              <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                <div className="flex items-center gap-3">
                  <Calendar className="text-cyan-400" size={18} />
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-widest">
                    {datePickerTarget === 'start' ? 'Start Date' : 'End Date'}
                  </h3>
                </div>
                <button onClick={() => setIsDatePickerOpen(false)} className="p-2 hover:bg-slate-800 rounded-xl text-slate-500 transition-colors">
                  <X size={20} />
                </button>
              </div>

              <div className="p-6 space-y-6">
                <div className="flex justify-between items-center px-2">
                  <button
                    type="button"
                    onClick={() => setCalendarView(new Date(calendarView.getFullYear(), calendarView.getMonth() - 1, 1))}
                    className="p-1 hover:text-cyan-400 transition-colors"
                  >
                    <ChevronDown className="rotate-90" size={20} />
                  </button>
                  <span className="text-xs font-bold text-slate-100 uppercase tracking-[0.2em]">
                    {calendarView.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                  </span>
                  <button
                    type="button"
                    onClick={() => setCalendarView(new Date(calendarView.getFullYear(), calendarView.getMonth() + 1, 1))}
                    className="p-1 hover:text-cyan-400 transition-colors"
                  >
                    <ChevronDown className="-rotate-90" size={20} />
                  </button>
                </div>

                <div className="grid grid-cols-7 gap-1 text-center">
                  {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, idx) => (
                    <span key={`${day}-${idx}`} className="text-[10px] font-bold text-slate-600 mb-2">{day}</span>
                  ))}
                  {generateCalendarDays().map((date, idx) => {
                    if (!date) return <div key={`empty-${idx}`} />;

                    const dateStr = formatYMD(date);
                    const isSelected = form.watch(datePickerTarget === 'start' ? 'period_start' : 'period_end') === dateStr;
                    const isToday = formatYMD(today) === dateStr;

                    // Boundary enforcement
                    const isFuture = date > maxDate;
                    const isTooOld = date < minDate;
                    const isDisabled = isFuture || isTooOld;

                    return (
                      <button
                        key={idx}
                        type="button"
                        disabled={isDisabled}
                        onClick={() => {
                          form.setValue(datePickerTarget === 'start' ? 'period_start' : 'period_end', dateStr);
                          setIsDatePickerOpen(false);
                        }}
                        className={cn(
                          "aspect-square flex items-center justify-center rounded-lg text-[10px] font-mono transition-all relative overflow-hidden",
                          isSelected
                            ? "bg-cyan-500 text-slate-950 font-bold shadow-lg shadow-cyan-500/20"
                            : isToday
                              ? "text-cyan-400 border border-cyan-400/20"
                              : "text-slate-400 hover:bg-slate-800 hover:text-slate-100",
                          isDisabled && "opacity-20 cursor-not-allowed grayscale bg-slate-950/50"
                        )}
                      >
                        {date.getDate()}
                      </button>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isTimeframeOpen && (
          <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/40 backdrop-blur-sm p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4"
            >
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <Clock className="text-cyan-400" size={18} />
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-widest">Select Interval</h3>
                </div>
                <button onClick={() => setIsTimeframeOpen(false)} className="p-1 hover:bg-slate-800 rounded-lg text-slate-500" type="button">
                  <X size={18} />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "15Min", label: "15 MINUTES" },
                  { id: "1H", label: "1 HOUR" },
                  { id: "2H", label: "2 HOURS" },
                  { id: "4H", label: "4 HOURS" },
                  { id: "12H", label: "12 HOURS" },
                  { id: "1D", label: "1 DAY" }
                ].map(tf => (
                  <button
                    key={tf.id}
                    type="button"
                    onClick={() => {
                      form.setValue("timeframe", tf.id as StrategyCreate['timeframe']);
                      setIsTimeframeOpen(false);
                    }}
                    className={cn(
                      "p-3 rounded-xl border text-[10px] font-bold transition-all text-center tracking-widest",
                      form.watch("timeframe") === tf.id
                        ? "bg-cyan-500 text-slate-950 border-cyan-500"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                    )}
                  >
                    {tf.label}
                  </button>
                ))}
              </div>
              <p className="text-[9px] text-slate-500 text-center uppercase tracking-tighter">Institutional Feeds only support 15m intervals or higher</p>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
