/**
 * Date bounds for the in-place date editor. A backtest tests the past, so no
 * card may offer a date after the current day: the picker clamps to today and
 * anything typed past it refuses immediately, before any round trip.
 *
 * The advertised `max_end` is the server's word for the current day at the
 * moment the card was built, not a durable data limit. A pending card can be
 * reopened days later, so a stale advertisement must never tighten the bound
 * below the browser's current day; the later of the two wins. When the
 * advertisement is ahead of the local clock (midnight skew), it still
 * extends the bound, and the server re-validates every submit either way,
 * with its typed refusal rendered on the card. A genuine data-coverage
 * ceiling would need its own advertised field, not this one.
 */

export function localTodayIso(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function effectiveMaxEndDate(
  advertisedMaxEnd: string | undefined,
  now: Date = new Date(),
): string {
  const today = localTodayIso(now);
  if (typeof advertisedMaxEnd === "string" && advertisedMaxEnd) {
    return advertisedMaxEnd > today ? advertisedMaxEnd : today;
  }
  return today;
}
