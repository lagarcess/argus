export type CompactDateRange = {
  start: string;
  end: string;
};

export function compactDateRangeDisplay(
  dateRange: CompactDateRange | null | undefined,
  locale: string,
): string | null {
  const start = parseIsoCalendarDate(dateRange?.start);
  const end = parseIsoCalendarDate(dateRange?.end);
  if (!start || !end) {
    return null;
  }
  const formatter = new Intl.DateTimeFormat(locale || "en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
  return `${formatter.format(start)} \u2192 ${formatter.format(end)}`;
}

function parseIsoCalendarDate(value: string | null | undefined): Date | null {
  const parts = value?.split("-").map((part) => Number(part));
  if (!parts || parts.length !== 3) {
    return null;
  }
  const [year, month, day] = parts;
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    !Number.isInteger(day) ||
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31
  ) {
    return null;
  }
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return parsed;
}
