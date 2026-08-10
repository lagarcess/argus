import { describe, expect, test } from "bun:test";

import { effectiveMaxEndDate, localTodayIso } from "../lib/date-edit-bounds";

describe("date edit bounds", () => {
  test("local today is the browser's calendar day, not UTC", () => {
    // 23:30 local on Jan 3 must stay Jan 3 wherever UTC has moved on to.
    const lateEvening = new Date(2026, 0, 3, 23, 30, 0);
    expect(localTodayIso(lateEvening)).toBe("2026-01-03");
    const earlyMorning = new Date(2026, 11, 31, 0, 5, 0);
    expect(localTodayIso(earlyMorning)).toBe("2026-12-31");
  });

  test("without an advertised bound the picker clamps to today", () => {
    const now = new Date(2026, 7, 10, 12, 0, 0);
    expect(effectiveMaxEndDate(undefined, now)).toBe("2026-08-10");
    expect(effectiveMaxEndDate("", now)).toBe("2026-08-10");
  });

  test("a stale advertisement never tightens below the current day", () => {
    const now = new Date(2026, 7, 10, 12, 0, 0);
    // The advertised bound is the server's today at card build. A card
    // reopened days later must offer everything up to the current day.
    expect(effectiveMaxEndDate("2026-08-07", now)).toBe("2026-08-10");
    expect(effectiveMaxEndDate("2026-08-09", now)).toBe("2026-08-10");
    // Same-day advertisement changes nothing.
    expect(effectiveMaxEndDate("2026-08-10", now)).toBe("2026-08-10");
  });

  test("an advertisement ahead of the local clock still extends", () => {
    // Midnight skew: the server's day rolled over first. Its word for the
    // current day wins; the server re-validates on submit either way.
    const now = new Date(2026, 7, 10, 23, 58, 0);
    expect(effectiveMaxEndDate("2026-08-11", now)).toBe("2026-08-11");
  });
});
