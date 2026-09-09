export type UsageWindow = {
  limit: number;
  used: number;
  remaining: number;
  period_end: string;
};

export type RegisteredUsageAllowance = {
  hour: UsageWindow;
  day: UsageWindow;
  guest_session: null;
  available_now: boolean;
  limiting_window: "hour" | "day";
};

export type GuestUsageAllowance = {
  hour: null;
  day: UsageWindow;
  guest_session: UsageWindow | null;
  available_now: boolean;
  limiting_window: "day" | "guest_session";
};

export type UsageAllowance = RegisteredUsageAllowance | GuestUsageAllowance;

/** No account window bounds this operation class, so nothing decrements. */
export type UnboundedAllowance = {
  hour: null;
  day: null;
  guest_session: null;
  available_now: true;
  limiting_window: null;
};

export type OperationClassAllowance = UsageAllowance | UnboundedAllowance;

export type UsageAllowanceResponse = {
  allowances: {
    compute: UnboundedAllowance;
    grounding: OperationClassAllowance;
    execution: UsageAllowance;
  };
};

/** What an API that has not deployed the operation classes yet answers. */
export type LegacyUsageAllowanceResponse = {
  allowances: {
    messages: UsageAllowance;
    backtests: UsageAllowance;
  };
};

export type RawUsageAllowanceResponse =
  | UsageAllowanceResponse
  | LegacyUsageAllowanceResponse;

export const UNBOUNDED_ALLOWANCE: UnboundedAllowance = {
  hour: null,
  day: null,
  guest_session: null,
  available_now: true,
  limiting_window: null,
};

/**
 * Rollout shim, removed together with the API's deprecated aliases. The web
 * and the API deploy independently, so a new bundle can meet an API that
 * still answers with messages and backtests only. Execution is that same
 * meter under its old name; the classes a legacy API does not report present
 * as unbounded until it does.
 */
function isOperationClassResponse(
  raw: RawUsageAllowanceResponse,
): raw is UsageAllowanceResponse {
  return "execution" in raw.allowances;
}

export function normalizeUsageAllowances(
  raw: RawUsageAllowanceResponse,
): UsageAllowanceResponse {
  if (isOperationClassResponse(raw)) return raw;
  return {
    allowances: {
      compute: UNBOUNDED_ALLOWANCE,
      grounding: UNBOUNDED_ALLOWANCE,
      execution: raw.allowances.backtests,
    },
  };
}

export function isUnboundedAllowance(
  allowance: OperationClassAllowance,
): allowance is UnboundedAllowance {
  return allowance.limiting_window === null;
}

export type AllowanceState = "zero" | "active" | "hourly_limited" | "exhausted";
export type AllowanceMeterTone = "teal" | "warning" | "danger";

function normalizedRemaining(window: UsageWindow): number {
  if (window.limit <= 0) return 0;
  return Math.max(0, Math.min(1, window.remaining / window.limit));
}

export function allowanceMeterTone(
  allowance: UsageAllowance,
): AllowanceMeterTone {
  const activeWindows = [allowance.hour, allowance.day].filter(
    (window): window is UsageWindow => window !== null,
  );
  const remainingCapacity = Math.min(
    ...activeWindows.map(normalizedRemaining),
  );

  if (remainingCapacity <= 0.1) return "danger";
  if (remainingCapacity < 0.3) return "warning";
  return "teal";
}

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
  limiting_window: "hour" | "day" | "guest_session";
}): boolean {
  return allowance.limiting_window === "hour";
}

export function showsWorkspaceWindow(allowance: {
  limiting_window: "hour" | "day" | "guest_session";
}): boolean {
  return allowance.limiting_window === "guest_session";
}

export function runActionIdempotencyKey(input: {
  type: string;
  payload?: Record<string, unknown>;
}): string | null {
  if (input.type !== "run_backtest") return null;
  const explicitKey = input.payload?.idempotency_key;
  if (typeof explicitKey === "string" && explicitKey.trim()) {
    return explicitKey.trim();
  }
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
