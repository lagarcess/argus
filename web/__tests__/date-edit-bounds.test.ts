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

  test("the earlier of the server bound and local today wins", () => {
    const now = new Date(2026, 7, 10, 12, 0, 0);
    // Server trails the browser around midnight: its bound tightens.
    expect(effectiveMaxEndDate("2026-08-09", now)).toBe("2026-08-09");
    // A server bound at or past local today never loosens the clamp.
    expect(effectiveMaxEndDate("2026-08-10", now)).toBe("2026-08-10");
    expect(effectiveMaxEndDate("2026-08-11", now)).toBe("2026-08-10");
  });
});
