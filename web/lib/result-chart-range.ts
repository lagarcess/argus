import type {
  ResultChartExplorationPolicy,
  ResultChartMarker,
  ResultChartMarkerSummary,
  ResultChartPoint,
} from "@/components/chat/types";

export type ResultChartRangeKey =
  | "1D"
  | "1W"
  | "1M"
  | "3M"
  | "YTD"
  | "1Y"
  | "ALL";
export type ResultChartSelection = ResultChartRangeKey | "CUSTOM";

export type ResultChartViewport = {
  startIndex: number;
  endIndex: number;
  startTime: string;
  endTime: string;
};

export type ResultChartRangeOption = ResultChartViewport & {
  key: ResultChartRangeKey;
};

export type ResultChartCustomError =
  | "missing_date"
  | "start_after_end"
  | "insufficient_observations";

export type ResultChartCustomResult =
  | { ok: true; range: ResultChartViewport }
  | { ok: false; error: ResultChartCustomError };

export type VisibleResultChartEvent = {
  marker: ResultChartMarker;
  sourceIndex: number;
};

export type VisibleResultChartSummary = {
  startTime: string;
  endTime: string;
  peak: ResultChartPoint;
  low: ResultChartPoint;
  suppliedEventCount: number;
  displayedEvents: VisibleResultChartEvent[];
  eventListSampled: boolean;
  markerSummary?: ResultChartMarkerSummary;
};

const DEFAULT_MINIMUM_VISIBLE_OBSERVATIONS = 6;
const DEFAULT_EVENT_LIMIT = 20;
const NON_ALL_RANGE_CAP = 4;

type NormalizedPoint = {
  ms: number;
  index: number;
  time: string;
  value: number;
};

export function deriveResultChartRanges(
  series: ResultChartPoint[],
  policy?: ResultChartExplorationPolicy | null,
): ResultChartRangeOption[] {
  const points = normalizedSeries(series);
  const minimumObservations = resolveMinimumObservations(policy);
  if (points.length < minimumObservations) return [];

  const first = points[0]!;
  const anchor = points[points.length - 1]!;
  const anchorDate = new Date(anchor.ms);
  const minimumDurationBoundary = meaningfulDurationBoundary(
    anchorDate,
    policy?.minimum_meaningful_duration,
  );

  const eligible: ResultChartRangeOption[] = [];
  const preferred: ResultChartRangeOption[] = [];
  for (const candidate of candidateBoundaries(anchorDate)) {
    if (candidate.key === "YTD" && first.ms >= candidate.boundaryMs) continue;
    const startPosition = firstPositionAtOrAfter(points, candidate.boundaryMs);
    const visibleCount = points.length - startPosition;
    const excludesSomething = startPosition > 0;
    const start = points[startPosition];
    if (
      !start ||
      visibleCount < minimumObservations ||
      !excludesSomething ||
      start.ms >= anchor.ms
    ) {
      continue;
    }
    const option: ResultChartRangeOption = {
      key: candidate.key,
      startIndex: start.index,
      endIndex: anchor.index,
      startTime: start.time,
      endTime: anchor.time,
    };
    eligible.push(option);
    if (
      minimumDurationBoundary == null ||
      candidate.boundaryMs <= minimumDurationBoundary
    ) {
      preferred.push(option);
    }
  }

  const shortlisted = (preferred.length > 0 ? preferred : eligible).slice(
    0,
    NON_ALL_RANGE_CAP,
  );
  return [
    ...shortlisted,
    {
      key: "ALL",
      startIndex: first.index,
      endIndex: anchor.index,
      startTime: first.time,
      endTime: anchor.time,
    },
  ];
}

export function resolveCustomResultChartRange(
  series: ResultChartPoint[],
  startDate: string,
  endDate: string,
): ResultChartCustomResult {
  const startDayMs = utcDateOnlyMs(startDate);
  const endDayMs = utcDateOnlyMs(endDate);
  if (startDayMs == null || endDayMs == null) {
    return { ok: false, error: "missing_date" };
  }
  if (startDayMs > endDayMs) {
    return { ok: false, error: "start_after_end" };
  }

  const points = normalizedSeries(series);
  const endOfEndDayMs = endDayMs + 24 * 60 * 60 * 1000 - 1;
  const startPosition = firstPositionAtOrAfter(points, startDayMs);
  const endPosition = lastPositionAtOrBefore(points, endOfEndDayMs);
  if (
    startPosition >= points.length ||
    endPosition < 0 ||
    endPosition - startPosition + 1 < 2
  ) {
    return { ok: false, error: "insufficient_observations" };
  }

  const start = points[startPosition]!;
  const end = points[endPosition]!;
  return {
    ok: true,
    range: {
      startIndex: start.index,
      endIndex: end.index,
      startTime: start.time,
      endTime: end.time,
    },
  };
}

export function summarizeVisibleResultChartRange(input: {
  series: ResultChartPoint[];
  markers?: ResultChartMarker[];
  markerSummary?: ResultChartMarkerSummary | null;
  startIndex: number;
  endIndex: number;
  eventLimit?: number;
}): VisibleResultChartSummary | null {
  const from = Math.max(0, Math.min(input.startIndex, input.endIndex));
  const to = Math.min(
    input.series.length - 1,
    Math.max(input.startIndex, input.endIndex),
  );

  let firstVisible: NormalizedPoint | null = null;
  let lastVisible: NormalizedPoint | null = null;
  let peak: NormalizedPoint | null = null;
  let low: NormalizedPoint | null = null;
  for (let index = from; index <= to; index += 1) {
    const point = input.series[index];
    const ms = point == null ? null : parseChartTimeMs(point.time);
    if (point == null || ms == null || !Number.isFinite(point.value)) continue;
    const normalized: NormalizedPoint = {
      ms,
      index,
      time: point.time,
      value: point.value,
    };
    if (firstVisible == null || ms < firstVisible.ms) firstVisible = normalized;
    if (lastVisible == null || ms > lastVisible.ms) lastVisible = normalized;
    if (peak == null || point.value > peak.value) peak = normalized;
    if (low == null || point.value < low.value) low = normalized;
  }
  if (firstVisible == null || lastVisible == null || peak == null || low == null) {
    return null;
  }
  const visibleStartMs = firstVisible.ms;
  const visibleEndMs = lastVisible.ms;

  const visibleEvents: Array<VisibleResultChartEvent & { ms: number }> = [];
  (input.markers ?? []).forEach((marker, sourceIndex) => {
    const ms = parseChartTimeMs(marker.time);
    if (ms == null || ms < visibleStartMs || ms > visibleEndMs) return;
    visibleEvents.push({ marker, sourceIndex, ms });
  });
  visibleEvents.sort((a, b) => a.ms - b.ms || a.sourceIndex - b.sourceIndex);

  const eventLimit = input.eventLimit ?? DEFAULT_EVENT_LIMIT;
  const displayedEvents = sampleEvenly(visibleEvents, eventLimit).map(
    ({ marker, sourceIndex }) => ({ marker, sourceIndex }),
  );

  return {
    startTime: firstVisible.time,
    endTime: lastVisible.time,
    peak: { time: peak.time, value: peak.value },
    low: { time: low.time, value: low.value },
    suppliedEventCount: visibleEvents.length,
    displayedEvents,
    eventListSampled: displayedEvents.length < visibleEvents.length,
    ...(input.markerSummary ? { markerSummary: input.markerSummary } : {}),
  };
}

function resolveMinimumObservations(
  policy?: ResultChartExplorationPolicy | null,
): number {
  const value = policy?.minimum_visible_observations;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    return DEFAULT_MINIMUM_VISIBLE_OBSERVATIONS;
  }
  return value;
}

function normalizedSeries(series: ResultChartPoint[]): NormalizedPoint[] {
  const points: NormalizedPoint[] = [];
  series.forEach((point, index) => {
    const ms = parseChartTimeMs(point.time);
    if (ms == null || !Number.isFinite(point.value)) return;
    points.push({ ms, index, time: point.time, value: point.value });
  });
  points.sort((a, b) => a.ms - b.ms || a.index - b.index);
  return points.filter(
    (point, position) => position === 0 || point.ms !== points[position - 1]!.ms,
  );
}

type CandidateBoundary = {
  key: Exclude<ResultChartRangeKey, "ALL">;
  boundaryMs: number;
};

function candidateBoundaries(anchor: Date): CandidateBoundary[] {
  return [
    { key: "1D", boundaryMs: shiftUtcDays(anchor, -1) },
    { key: "1W", boundaryMs: shiftUtcDays(anchor, -7) },
    { key: "1M", boundaryMs: shiftUtcMonths(anchor, -1) },
    { key: "3M", boundaryMs: shiftUtcMonths(anchor, -3) },
    { key: "YTD", boundaryMs: Date.UTC(anchor.getUTCFullYear(), 0, 1) },
    { key: "1Y", boundaryMs: shiftUtcMonths(anchor, -12) },
  ].sort(
    (a, b) => b.boundaryMs - a.boundaryMs,
  ) as CandidateBoundary[];
}

function shiftUtcDays(anchor: Date, days: number): number {
  return Date.UTC(
    anchor.getUTCFullYear(),
    anchor.getUTCMonth(),
    anchor.getUTCDate() + days,
    anchor.getUTCHours(),
    anchor.getUTCMinutes(),
    anchor.getUTCSeconds(),
  );
}

function shiftUtcMonths(anchor: Date, months: number): number {
  const year = anchor.getUTCFullYear();
  const month = anchor.getUTCMonth() + months;
  const lastDayOfTargetMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return Date.UTC(
    year,
    month,
    Math.min(anchor.getUTCDate(), lastDayOfTargetMonth),
    anchor.getUTCHours(),
    anchor.getUTCMinutes(),
    anchor.getUTCSeconds(),
  );
}

function meaningfulDurationBoundary(
  anchor: Date,
  duration?: string | null,
): number | null {
  const parsed = parseCalendarDuration(duration);
  if (parsed == null) return null;
  if (parsed.unit === "D") return shiftUtcDays(anchor, -parsed.amount);
  if (parsed.unit === "W") return shiftUtcDays(anchor, -parsed.amount * 7);
  if (parsed.unit === "M") return shiftUtcMonths(anchor, -parsed.amount);
  return shiftUtcMonths(anchor, -parsed.amount * 12);
}

function parseCalendarDuration(
  duration?: string | null,
): { amount: number; unit: "D" | "W" | "M" | "Y" } | null {
  if (typeof duration !== "string" || duration.length < 3) return null;
  if (duration[0] !== "P") return null;
  const unit = duration[duration.length - 1];
  if (unit !== "D" && unit !== "W" && unit !== "M" && unit !== "Y") return null;
  const digits = duration.slice(1, -1);
  if (digits.length === 0) return null;
  for (let index = 0; index < digits.length; index += 1) {
    const code = digits.charCodeAt(index);
    if (code < 48 || code > 57) return null;
  }
  const amount = Number.parseInt(digits, 10);
  if (!Number.isInteger(amount) || amount < 1) return null;
  return { amount, unit };
}

function firstPositionAtOrAfter(points: NormalizedPoint[], ms: number): number {
  let lowIndex = 0;
  let highIndex = points.length;
  while (lowIndex < highIndex) {
    const middle = (lowIndex + highIndex) >> 1;
    if (points[middle]!.ms < ms) lowIndex = middle + 1;
    else highIndex = middle;
  }
  return lowIndex;
}

function lastPositionAtOrBefore(points: NormalizedPoint[], ms: number): number {
  return firstPositionAtOrAfter(points, ms + 1) - 1;
}

function sampleEvenly<T>(items: T[], limit: number): T[] {
  if (limit < 1) return [];
  if (items.length <= limit) return [...items];
  if (limit === 1) return [items[0]!];
  const positions = new Set<number>();
  const step = (items.length - 1) / (limit - 1);
  for (let slot = 0; slot < limit; slot += 1) {
    positions.add(Math.round(slot * step));
  }
  return [...positions].sort((a, b) => a - b).map((position) => items[position]!);
}

// UTC parsing mirrors the chart adapter's accepted formats ("YYYY-MM-DD" and
// "YYYY-MM-DDTHH:MM[:SS]"); anything else is excluded from policy math.
function parseChartTimeMs(value: string): number | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  const dateOnly = utcDateOnlyMs(trimmed);
  if (dateOnly != null) return dateOnly;
  if (trimmed.length < 16 || trimmed[10] !== "T" || trimmed[13] !== ":") {
    return null;
  }
  const dayMs = utcDateOnlyMs(trimmed.slice(0, 10));
  const hour = fixedDigits(trimmed.slice(11, 13), 2);
  const minute = fixedDigits(trimmed.slice(14, 16), 2);
  const second =
    trimmed.length >= 19 && trimmed[16] === ":"
      ? fixedDigits(trimmed.slice(17, 19), 2)
      : "00";
  if (dayMs == null || hour == null || minute == null || second == null) {
    return null;
  }
  return (
    dayMs +
    Number(hour) * 60 * 60 * 1000 +
    Number(minute) * 60 * 1000 +
    Number(second) * 1000
  );
}

function utcDateOnlyMs(value: string): number | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed.length !== 10 || trimmed[4] !== "-" || trimmed[7] !== "-") {
    return null;
  }
  const year = fixedDigits(trimmed.slice(0, 4), 4);
  const month = fixedDigits(trimmed.slice(5, 7), 2);
  const day = fixedDigits(trimmed.slice(8, 10), 2);
  if (year == null || month == null || day == null) return null;
  const monthNumber = Number(month);
  const dayNumber = Number(day);
  if (monthNumber < 1 || monthNumber > 12 || dayNumber < 1 || dayNumber > 31) {
    return null;
  }
  return Date.UTC(Number(year), monthNumber - 1, dayNumber);
}

function fixedDigits(value: string, length: number): string | null {
  if (value.length !== length) return null;
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code < 48 || code > 57) return null;
  }
  return value;
}
