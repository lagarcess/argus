/**
 * Date bounds for the in-place date editor. A backtest tests the past, so no
 * card, with or without an advertised envelope, may offer a date after the
 * current day: the picker clamps to today and anything typed past it refuses
 * immediately, before any round trip. The server's advertised bound can only
 * tighten this further (its today may trail the browser's around midnight);
 * the earlier of the two wins, so the client never offers a date the backend
 * will refuse.
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
    return advertisedMaxEnd < today ? advertisedMaxEnd : today;
  }
  return today;
}
