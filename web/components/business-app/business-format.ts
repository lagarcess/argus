/** A currency the owner can read without guessing which dollar it is. */
const CURRENCY_PREFIX: Record<string, string> = { DOP: "RD$", USD: "US$" };

export function formatMoney(
  amount: string | null,
  currency: string | null,
  locale: string,
): string {
  if (amount === null || currency === null) return "";
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${currency} ${amount}`;
  const number = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return `${CURRENCY_PREFIX[currency] ?? currency} ${number}`;
}

export function formatDay(day: string | null, locale: string): string {
  if (!day) return "";
  const date = new Date(`${day.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return day;
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric" }).format(date);
}

export function formatRelativeTime(iso: string | null, locale: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.round((then - Date.now()) / 60_000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (Math.abs(minutes) < 60) return rtf.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return rtf.format(hours, "hour");
  return rtf.format(Math.round(hours / 24), "day");
}

export type Period = { key: "this_month" | "last_month" | "last_30_days"; from: string; to: string };

function isoDay(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

export function periodRange(key: Period["key"], now = new Date()): Period {
  if (key === "last_month") {
    const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const last = new Date(now.getFullYear(), now.getMonth(), 0);
    return { key, from: isoDay(first), to: isoDay(last) };
  }
  if (key === "last_30_days") {
    const start = new Date(now);
    start.setDate(start.getDate() - 29);
    return { key, from: isoDay(start), to: isoDay(now) };
  }
  return { key, from: isoDay(new Date(now.getFullYear(), now.getMonth(), 1)), to: isoDay(now) };
}

export const RECEIPT_CATEGORY_IDS = [
  "other",
  "groceries",
  "dining",
  "transport",
  "housing",
  "health",
  "shopping",
  "interest_fees",
] as const;

/** "12,50" is a decimal comma; any other shape goes to the backend as typed. */
export function normalizeAmount(raw: string): string {
  const value = raw.trim();
  return !value.includes(".") && value.split(",").length === 2 ? value.replace(",", ".") : value;
}
