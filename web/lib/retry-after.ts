import { useEffect, useState } from "react";

export const RETRY_AFTER_FALLBACK_SECONDS = 15;
export const RETRY_AFTER_MIN_SECONDS = 1;
export const RETRY_AFTER_MAX_SECONDS = 120;

function clampRetryAfterSeconds(seconds: number): number {
  if (!Number.isFinite(seconds)) {
    return RETRY_AFTER_FALLBACK_SECONDS;
  }
  return Math.min(
    RETRY_AFTER_MAX_SECONDS,
    Math.max(RETRY_AFTER_MIN_SECONDS, Math.trunc(seconds)),
  );
}

const IMF_FIXDATE =
  /^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4} \d{2}:\d{2}:\d{2} GMT$/;
const RFC_850_DATE =
  /^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), \d{2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2} \d{2}:\d{2}:\d{2} GMT$/;
const ASCTIME_DATE =
  /^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (?: \d|\d{2}) \d{2}:\d{2}:\d{2} \d{4}$/;

export function isHttpRetryAfterDate(value: string): boolean {
  return IMF_FIXDATE.test(value) || RFC_850_DATE.test(value) || ASCTIME_DATE.test(value);
}

export function parseRetryAfterSeconds(
  value: string | null | undefined,
  nowMs: number = Date.now(),
): number {
  const text = value?.trim() ?? "";
  if (!text) {
    return RETRY_AFTER_FALLBACK_SECONDS;
  }
  if (/^\d+$/.test(text)) {
    return clampRetryAfterSeconds(Number(text));
  }
  if (!isHttpRetryAfterDate(text)) {
    return RETRY_AFTER_FALLBACK_SECONDS;
  }
  const parsed = Date.parse(text);
  if (!Number.isFinite(parsed)) {
    return RETRY_AFTER_FALLBACK_SECONDS;
  }
  return clampRetryAfterSeconds(Math.ceil((parsed - nowMs) / 1000));
}

export function remainingRetryAfterSeconds(
  availableAtMs: number | undefined,
  nowMs: number,
): number {
  if (availableAtMs == null) {
    return 0;
  }
  return Math.max(0, Math.ceil((availableAtMs - nowMs) / 1000));
}

export function shouldKeepRetryAfterTicker(
  availableAtMs: number | undefined,
  nowMs: number,
): boolean {
  return remainingRetryAfterSeconds(availableAtMs, nowMs) > 0;
}

export function useRetryAfterCountdown(availableAtMs?: number): number {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const tick = () => {
      const nextNowMs = Date.now();
      setNowMs(nextNowMs);
      return shouldKeepRetryAfterTicker(availableAtMs, nextNowMs);
    };
    if (!tick()) {
      return;
    }
    const id = window.setInterval(() => {
      if (!tick()) {
        window.clearInterval(id);
      }
    }, 250);
    return () => window.clearInterval(id);
  }, [availableAtMs]);

  return remainingRetryAfterSeconds(availableAtMs, nowMs);
}
