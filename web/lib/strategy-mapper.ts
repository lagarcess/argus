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

const EXECUTION_KEYS = new Set([
  "capital",
  "trade_direction",
  "participation_rate",
  "execution_priority",
  "va_sensitivity",
  "slippage_model",
]);

export function builderToStrategyCreatePayload(data: StrategyCreate): StrategySchema {
  const indicatorsConfig: Record<string, number | boolean | string> = {
    ...data.parameters,
    capital: data.capital,
    trade_direction: data.trade_direction,
    participation_rate: data.participation_rate,
    execution_priority: data.execution_priority,
    va_sensitivity: data.va_sensitivity,
    slippage_model: data.slippage_model,
  };

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
    indicators_config: indicatorsConfig,
    capital: data.capital,
    trade_direction: data.trade_direction,
    participation_rate: data.participation_rate,
    execution_priority: data.execution_priority,
    va_sensitivity: data.va_sensitivity,
    slippage_model: data.slippage_model,
  };
}

export function strategyToBuilderForm(strategy: StrategySchema): Partial<StrategyCreate> {
  const symbol = strategy.symbols?.[0] ?? "AAPL";
  const indicatorsConfig = (strategy.indicators_config ?? {}) as Record<string, unknown>;
  const parameterEntries = Object.entries(indicatorsConfig).filter(
    ([key, value]) =>
      !EXECUTION_KEYS.has(key) &&
      (typeof value === "number" || typeof value === "boolean"),
  );

  const capital =
    typeof strategy.capital === "number"
      ? strategy.capital
      : typeof indicatorsConfig.capital === "number"
        ? indicatorsConfig.capital
        : 100000;
  const tradeDirection =
    strategy.trade_direction === "SHORT" || strategy.trade_direction === "BOTH"
      ? strategy.trade_direction
      : indicatorsConfig.trade_direction === "SHORT" ||
          indicatorsConfig.trade_direction === "BOTH"
        ? (indicatorsConfig.trade_direction as "SHORT" | "BOTH")
        : "LONG";
  const participationRate =
    typeof strategy.participation_rate === "number"
      ? strategy.participation_rate
      : typeof indicatorsConfig.participation_rate === "number"
        ? indicatorsConfig.participation_rate
        : 0.1;
  const executionPriority =
    typeof strategy.execution_priority === "number"
      ? strategy.execution_priority
      : typeof indicatorsConfig.execution_priority === "number"
        ? indicatorsConfig.execution_priority
        : 1.0;
  const vaSensitivity =
    typeof strategy.va_sensitivity === "number"
      ? strategy.va_sensitivity
      : typeof indicatorsConfig.va_sensitivity === "number"
        ? indicatorsConfig.va_sensitivity
        : 1.0;
  const slippageModel =
    strategy.slippage_model === "fixed"
      ? "fixed"
      : indicatorsConfig.slippage_model === "fixed"
        ? "fixed"
        : "vol_adjusted";

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
    parameters: Object.fromEntries(parameterEntries) as Record<string, number | boolean>,
    capital,
    trade_direction: tradeDirection,
    participation_rate: participationRate,
    execution_priority: executionPriority,
    va_sensitivity: vaSensitivity,
    slippage_model: slippageModel,
    stop_loss_pct: strategy.stop_loss_pct,
    take_profit_pct: strategy.take_profit_pct,
  };
}
