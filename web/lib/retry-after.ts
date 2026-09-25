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

export function parseRetryAfterSeconds(
  value: string | null | undefined,
  nowMs: number = Date.now(),
): number {
  const text = value?.trim() ?? "";
  if (!text) {
    return RETRY_AFTER_FALLBACK_SECONDS;
  }
  if (/^[0-9]+$/.test(text)) {
    return clampRetryAfterSeconds(Number(text));
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

export function useRetryAfterCountdown(availableAtMs?: number): number {
  const [remaining, setRemaining] = useState(() =>
    remainingRetryAfterSeconds(availableAtMs, Date.now()),
  );

  useEffect(() => {
    const tick = () =>
      setRemaining(remainingRetryAfterSeconds(availableAtMs, Date.now()));
    tick();
    if (remainingRetryAfterSeconds(availableAtMs, Date.now()) <= 0) {
      return;
    }
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [availableAtMs]);

  return remaining;
}
