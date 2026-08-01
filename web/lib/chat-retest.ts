import type { ChatActionOption, Message } from "@/components/chat/types";

export const RETEST_ACTION_TYPE = "retest_run" as const;
export const RETEST_ACTION_LABEL_KEY = "command_palette.retest_current_data";
export const RETEST_CONTRACT_VERSION = "argus_retest_run/v1";
export const RETEST_WINDOW_POLICY = "same_duration_ending_today";

export type RetestDurationUnit = "year" | "month" | "day";

/** Backend-owned display context; the transcript localizes it on render. */
export type RetestReceipt = {
  sourceRunId: string;
  symbols: string[];
  strategyFamily: string;
  durationDays: number;
  duration: { unit: RetestDurationUnit; count: number };
  cadence: string | null;
  timeframe: string | null;
};

type Translate = (
  key: string,
  defaultValue: string,
  options?: Record<string, unknown>,
) => string;

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : null;
}

function durationUnit(value: unknown): RetestDurationUnit | null {
  return value === "year" || value === "month" || value === "day" ? value : null;
}

/**
 * The client submits identity and policy only; every executable field is
 * reloaded server-side from the owner-scoped stored run.
 */
export function retestActionOption(sourceRunId: string): ChatActionOption {
  return {
    id: `retest-run-${sourceRunId}`,
    label: "Retest with current data",
    labelKey: RETEST_ACTION_LABEL_KEY,
    type: RETEST_ACTION_TYPE,
    payload: {
      source_run_id: sourceRunId,
      window_policy: RETEST_WINDOW_POLICY,
      contract_version: RETEST_CONTRACT_VERSION,
    },
  };
}

export function retestReceiptFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
): RetestReceipt | null {
  const receipt = recordOrNull(metadata?.retest_receipt);
  const sourceRunId = stringOrNull(receipt?.source_run_id);
  const strategyFamily = stringOrNull(receipt?.strategy_family);
  const duration = recordOrNull(receipt?.duration);
  const unit = durationUnit(duration?.unit);
  const count = typeof duration?.count === "number" ? duration.count : null;
  const durationDays =
    typeof receipt?.duration_days === "number" ? receipt.duration_days : null;
  if (!sourceRunId || !strategyFamily || !unit || count === null || durationDays === null) {
    return null;
  }
  const symbols = Array.isArray(receipt?.symbols)
    ? receipt.symbols
        .map((symbol) => stringOrNull(symbol))
        .filter((symbol): symbol is string => symbol !== null)
    : [];
  return {
    sourceRunId,
    symbols,
    strategyFamily,
    durationDays,
    duration: { unit, count },
    cadence: stringOrNull(receipt?.cadence),
    timeframe: stringOrNull(receipt?.timeframe),
  };
}

export function retestReceiptFromFinalPayload(
  payload: Record<string, unknown>,
): RetestReceipt | null {
  return retestReceiptFromMetadata(payload);
}

const STRATEGY_FAMILY_DEFAULTS: Record<string, string> = {
  buy_and_hold: "Buy and hold",
  dca_accumulation: "Recurring buys",
  indicator_threshold: "Indicator threshold",
  signal_strategy: "Signal rules",
};

export function retestStrategyFamilyLabel(
  receipt: RetestReceipt,
  t: Translate,
): string {
  return t(
    `chat.retest.strategy_family.${receipt.strategyFamily}`,
    STRATEGY_FAMILY_DEFAULTS[receipt.strategyFamily] ?? receipt.strategyFamily,
  );
}

export function retestDurationLabel(
  receipt: RetestReceipt,
  t: Translate,
): string {
  const { unit, count } = receipt.duration;
  const defaults: Record<RetestDurationUnit, string> = {
    year: "same {{count}}-year duration",
    month: "same {{count}}-month duration",
    day: "same {{count}}-day duration",
  };
  return t(`chat.retest.duration.${unit}`, defaults[unit], { count });
}

/** `GLD · Buy and hold · same 1-year duration` */
export function retestReceiptContextLine(
  receipt: RetestReceipt,
  t: Translate,
): string {
  return [
    receipt.symbols.join(", "),
    retestStrategyFamilyLabel(receipt, t),
    retestDurationLabel(receipt, t),
  ]
    .filter((part) => part.length > 0)
    .join(" · ");
}

/**
 * The receipt is backend truth, so the optimistic action bubble stays a
 * one-liner until the turn's own response supplies it.
 */
export function applyRetestReceipt(
  messages: Message[],
  userMessageId: string,
  receipt: RetestReceipt | null,
): Message[] {
  if (!receipt) return messages;
  return messages.map((message) =>
    message.id === userMessageId && message.role === "user"
      ? { ...message, retestReceipt: receipt }
      : message,
  );
}
