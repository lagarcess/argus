import { describe, expect, test } from "bun:test";
import {
  businessPath,
  businessPreviewEnabled,
  resolveBusinessPathname,
} from "../lib/business-site";
import {
  formatSampleMoney,
  getSampleSummary,
  sampleMonths,
} from "../components/business/sample-data";

describe("isolated business preview", () => {
  test.each([undefined, "", "false", "1", "TRUE"])(
    "fails closed for %s",
    (value) => {
      expect(businessPreviewEnabled(value)).toBe(false);
    },
  );
  test("opens only with the explicit local preview value", () => {
    expect(businessPreviewEnabled("true")).toBe(true);
  });
  test.each(["es", "en"] as const)("resolves all %s surfaces", (locale) => {
    for (const page of ["home", "demo", "personal"] as const) {
      expect(resolveBusinessPathname(businessPath(locale, page))).toEqual({
        locale,
        page,
      });
    }
  });
  test.each([
    null,
    "/",
    "/chat",
    "/business-old",
    "/business/private",
    "/business/en/demo/extra",
    "/business/es",
  ])("does not claim another app route: %s", (path) => {
    expect(resolveBusinessPathname(path)).toBeNull();
  });
});

describe("illustrative business money", () => {
  test("keeps receivables separate from cash received", () => {
    const summary = getSampleSummary();
    expect(summary).toEqual({
      income: 245000,
      expenses: 168500,
      difference: 76500,
      receivables: 105500,
    });
    expect(sampleMonths[4].expenses).toBe(summary.expenses);
  });
  test.each(["es", "en"] as const)(
    "shows the original Dominican currency in %s",
    (locale) => {
      expect(formatSampleMoney(76500, locale)).toBe("RD$ 76,500");
    },
  );
});
