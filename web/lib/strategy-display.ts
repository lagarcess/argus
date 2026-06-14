import type { TFunction } from "i18next";
import type {
  StrategyConfirmationPayload,
  StrategyResultPayload,
} from "@/components/chat/types";

const STRATEGY_TYPE_FALLBACKS = {
  buy_and_hold: "Buy and Hold",
  dca_accumulation: "Recurring Buys",
  indicator_threshold: "RSI Threshold",
  signal_strategy: "Moving Average Crossover",
} as const;

type StrategyTypeKey = keyof typeof STRATEGY_TYPE_FALLBACKS;

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

export function canonicalStrategyType(
  value: unknown,
): StrategyTypeKey | undefined {
  const normalized = stringValue(value)?.toLowerCase().replaceAll("-", "_");
  if (!normalized) return undefined;
  return normalized in STRATEGY_TYPE_FALLBACKS
    ? (normalized as StrategyTypeKey)
    : undefined;
}

export function strategyTypeFromResult(
  result: Pick<StrategyResultPayload, "template" | "configSnapshot">,
) {
  const config = recordValue(result.configSnapshot);
  const resolvedStrategy = recordValue(config?.resolved_strategy);
  const resolvedParameters = recordValue(config?.resolved_parameters);

  return (
    canonicalStrategyType(result.template) ??
    canonicalStrategyType(config?.template) ??
    canonicalStrategyType(resolvedStrategy?.strategy_type) ??
    canonicalStrategyType(resolvedParameters?.strategy_type)
  );
}

export function strategyTypeFromConfirmation(
  confirmation: Pick<StrategyConfirmationPayload, "strategy_type">,
) {
  return canonicalStrategyType(confirmation.strategy_type);
}

export function strategyDisplayLabel(
  strategyType: string | null | undefined,
  t?: TFunction,
  fallback?: string | null,
) {
  const canonical = canonicalStrategyType(strategyType);
  const fallbackLabel =
    (canonical ? STRATEGY_TYPE_FALLBACKS[canonical] : undefined) ??
    stringValue(fallback);
  if (!canonical) return fallbackLabel;
  return t
    ? t(`chat.strategy_type.${canonical}`, { defaultValue: fallbackLabel })
    : fallbackLabel;
}
