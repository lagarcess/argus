export type UsageWindow = {
  limit: number;
  used: number;
  remaining: number;
  period_end: string;
};

export type UsageAllowance = {
  hour: UsageWindow;
  day: UsageWindow;
  available_now: boolean;
  limiting_window: "hour" | "day";
};

export type UsageAllowanceResponse = {
  allowances: {
    messages: UsageAllowance;
    backtests: UsageAllowance;
  };
};

export type AllowanceState = "zero" | "active" | "hourly_limited" | "exhausted";

// Presentation state only: every input is backend-derived truth. The daily
// window owns the primary story; the hourly window explains availability
// whenever the backend marks it limiting.
export function classifyAllowance(allowance: {
  available_now: boolean;
  day: { used: number; remaining: number };
}): AllowanceState {
  if (allowance.day.remaining === 0) return "exhausted";
  if (!allowance.available_now) return "hourly_limited";
  if (allowance.day.used === 0) return "zero";
  return "active";
}

export function showsHourlyWindow(allowance: {
  limiting_window: "hour" | "day";
}): boolean {
  return allowance.limiting_window === "hour";
}

// The approved contract requires run_backtest actions to carry
// Idempotency-Key equal to the confirmation identity, so retries and
// reconnects replay the one durable admission instead of charging again.
export function runActionIdempotencyKey(input: {
  type: string;
  payload?: Record<string, unknown>;
}): string | null {
  if (input.type !== "run_backtest") return null;
  const confirmationId = input.payload?.confirmation_id;
  return typeof confirmationId === "string" && confirmationId.trim()
    ? confirmationId.trim()
    : null;
}

export function formatAllowancePeriodEnd(
  periodEnd: string,
  locale: string,
  timeZone?: string,
): string {
  const date = new Date(periodEnd);
  if (Number.isNaN(date.getTime())) return periodEnd;

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}
