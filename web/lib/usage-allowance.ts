export type AllowanceState = "zero" | "active" | "exhausted";

export function classifyAllowance(allowance: {
  used: number;
  remaining: number;
}): AllowanceState {
  if (allowance.remaining === 0) return "exhausted";
  if (allowance.used === 0) return "zero";
  return "active";
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
