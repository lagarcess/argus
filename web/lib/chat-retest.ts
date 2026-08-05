import type { ChatActionOption, Message } from "@/components/chat/types";
import { compactDateDisplay } from "@/lib/date-range-display";

export const RETEST_ACTION_TYPE = "retest_run" as const;
export const RETEST_ACTION_LABEL_KEY = "command_palette.retest_current_data";
export const RETEST_CONTRACT_VERSION = "argus_retest_run/v2";
export const RETEST_WINDOW_POLICY = "preserve_start_ending_latest_available";

export type RetestDurationUnit = "year" | "month" | "day";
export type RetestDateRange = { start: string; end: string };
export type RetestDuration = {
  unit: RetestDurationUnit;
  count: number;
  approximate: boolean;
};
export type RetestPeriodPayload = {
  original_date_range: RetestDateRange;
  requested_date_range: RetestDateRange;
  effective_date_range: RetestDateRange;
  duration_days: number;
  duration: RetestDuration;
};
export type RetestPeriod = {
  originalDateRange: RetestDateRange;
  requestedDateRange: RetestDateRange;
  effectiveDateRange: RetestDateRange;
  durationDays: number;
  duration: RetestDuration;
};

/** Backend-owned display context; the transcript localizes it on render. */
export type RetestReceipt = {
  sourceRunId: string;
  symbols: string[];
  strategyFamily: string;
  durationDays: number;
  duration: RetestDuration;
  cadence: string | null;
  timeframe: string | null;
  period: RetestPeriod | null;
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

function finiteNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function dateRangeOrNull(value: unknown): RetestDateRange | null {
  const record = recordOrNull(value);
  const start = stringOrNull(record?.start);
  const end = stringOrNull(record?.end);
  if (!start || !end || !isIsoCalendarDate(start) || !isIsoCalendarDate(end)) {
    return null;
  }
  if (start > end) return null;
  return { start, end };
}

function isIsoCalendarDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

function durationOrNull(value: unknown): RetestDuration | null {
  const duration = recordOrNull(value);
  const unit = durationUnit(duration?.unit);
  const count = finiteNumberOrNull(duration?.count);
  const approximate = duration?.approximate;
  if (!unit || count === null || count < 0 || typeof approximate !== "boolean") {
    return null;
  }
  return { unit, count, approximate };
}

export function retestPeriodFromValue(value: unknown): RetestPeriod | null {
  const period = recordOrNull(value);
  const originalDateRange = dateRangeOrNull(period?.original_date_range);
  const requestedDateRange = dateRangeOrNull(period?.requested_date_range);
  const effectiveDateRange = dateRangeOrNull(period?.effective_date_range);
  const durationDays = finiteNumberOrNull(period?.duration_days);
  const duration = durationOrNull(period?.duration);
  if (
    !originalDateRange ||
    !requestedDateRange ||
    !effectiveDateRange ||
    durationDays === null ||
    durationDays < 0 ||
    !Number.isInteger(durationDays) ||
    !duration
  ) {
    return null;
  }
  return {
    originalDateRange,
    requestedDateRange,
    effectiveDateRange,
    durationDays,
    duration,
  };
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
  const count = finiteNumberOrNull(duration?.count);
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
    duration: {
      unit,
      count,
      approximate: duration?.approximate === true,
    },
    cadence: stringOrNull(receipt?.cadence),
    timeframe: stringOrNull(receipt?.timeframe),
    period: retestPeriodFromValue(receipt),
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

export function retestPeriodTransformationLabel(
  period: RetestPeriod,
  locale: string,
): string {
  return `${dateRangeLabel(period.originalDateRange, locale)} → ${dateRangeLabel(
    period.effectiveDateRange,
    locale,
  )}`;
}

export function retestEffectiveDurationLabel(
  duration: RetestDuration,
  t: Translate,
  locale: string,
): string {
  const formattedCount = new Intl.NumberFormat(locale || "en", {
    maximumFractionDigits: 1,
  }).format(duration.count);
  const singular = duration.count === 1;
  const defaultUnit = singular ? duration.unit : `${duration.unit}s`;
  const qualifier = duration.approximate ? "about " : "";
  return t(
    `chat.retest.effective_duration.${
      duration.approximate ? "approximate" : "exact"
    }.${duration.unit}`,
    `${qualifier}{{formattedCount}} ${defaultUnit}`,
    { count: duration.count, formattedCount },
  );
}

function dateRangeLabel(dateRange: RetestDateRange, locale: string): string {
  return `${compactDateDisplay(dateRange.start, locale)} – ${compactDateDisplay(
    dateRange.end,
    locale,
  )}`;
}

/** `GLD · Buy and hold · same 1-year duration` */
export function retestReceiptContextLine(
  receipt: RetestReceipt,
  t: Translate,
  locale = "en",
): string {
  const periodParts = receipt.period
    ? [
        retestPeriodTransformationLabel(receipt.period, locale),
        retestEffectiveDurationLabel(receipt.period.duration, t, locale),
      ]
    : [retestDurationLabel(receipt, t)];
  return [
    receipt.symbols.join(", "),
    retestStrategyFamilyLabel(receipt, t),
    ...periodParts,
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
