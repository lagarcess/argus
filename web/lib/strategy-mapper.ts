import type { StrategyCreate } from "@/app/(protected)/builder/page";
import type { StrategySchema } from "@/lib/api/types.gen";

const TIMEFRAME_TO_API: Record<StrategyCreate["timeframe"], string> = {
  "15Min": "15Min",
  "1H": "1Hour",
  "2H": "1Hour",
  "4H": "4Hour",
  "12H": "4Hour",
  "1D": "1Day",
};

const API_TO_TIMEFRAME: Record<string, StrategyCreate["timeframe"]> = {
  "15Min": "15Min",
  "15m": "15Min",
  "1Hour": "1H",
  "1h": "1H",
  "4Hour": "4H",
  "4h": "4H",
  "1Day": "1D",
  "1d": "1D",
};

export function builderToStrategyCreatePayload(data: StrategyCreate): StrategySchema {
  return {
    name: data.name,
    symbols: [data.asset_symbol],
    timeframe: TIMEFRAME_TO_API[data.timeframe] ?? "1Hour",
    start_date: new Date(data.period_start).toISOString(),
    end_date: new Date(data.period_end).toISOString(),
    entry_criteria: data.entry_criteria,
    exit_criteria: data.exit_criteria,
    slippage: data.slippage_bps / 10000,
    fees: data.fees_per_trade_bps / 10000,
    stop_loss_pct: data.stop_loss_pct,
    take_profit_pct: data.take_profit_pct,
    indicators_config: data.parameters,
  };
}

export function strategyToBuilderForm(strategy: StrategySchema): Partial<StrategyCreate> {
  const symbol = strategy.symbols?.[0] ?? "AAPL";
  return {
    name: strategy.name ?? "",
    asset_symbol: symbol,
    timeframe: API_TO_TIMEFRAME[strategy.timeframe ?? "1Hour"] ?? "1H",
    period_start: strategy.start_date
      ? new Date(strategy.start_date).toISOString().slice(0, 10)
      : "2024-01-01",
    period_end: strategy.end_date
      ? new Date(strategy.end_date).toISOString().slice(0, 10)
      : new Date().toISOString().slice(0, 10),
    entry_criteria: (strategy.entry_criteria ?? []) as StrategyCreate["entry_criteria"],
    exit_criteria: (strategy.exit_criteria ?? []) as StrategyCreate["exit_criteria"],
    slippage_bps: (strategy.slippage ?? 0.001) * 10000,
    fees_per_trade_bps: (strategy.fees ?? 0.001) * 10000,
    parameters: (strategy.indicators_config ?? {}) as Record<string, number | boolean>,
    stop_loss_pct: strategy.stop_loss_pct,
    take_profit_pct: strategy.take_profit_pct,
  };
}
