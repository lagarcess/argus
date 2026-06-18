import { describe, expect, test } from "bun:test";

import { compactDateRangeDisplay } from "../lib/date-range-display";

describe("date range display", () => {
  const dateRange = { start: "2024-01-01", end: "2024-03-31" };

  test("formats compact English date ranges from canonical ISO dates", () => {
    expect(compactDateRangeDisplay(dateRange, "en-US")).toBe(
      "Jan 1, 2024 \u2192 Mar 31, 2024",
    );
  });

  test("formats compact Spanish date ranges from canonical ISO dates", () => {
    expect(compactDateRangeDisplay(dateRange, "es-419")).toBe(
      "1 ene 2024 \u2192 31 mar 2024",
    );
  });

  test("returns null when canonical dates are unavailable", () => {
    expect(compactDateRangeDisplay({ start: "", end: "2024-03-31" }, "es-419"))
      .toBeNull();
  });

  test("returns null for impossible calendar dates", () => {
    expect(
      compactDateRangeDisplay({ start: "2024-02-31", end: "2024-03-31" }, "en-US"),
    ).toBeNull();
  });
});
