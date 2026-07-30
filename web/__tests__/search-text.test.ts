import { describe, expect, test } from "bun:test";

import {
  PYTHON_CASEFOLD_UNICODE_VERSION,
  normalizeSearchText,
  normalizedSearchTokenSpans,
  searchHasIndexableToken,
} from "../lib/search-text";

describe("frontend search normalization", () => {
  test("is pinned to the Python 3.10 Unicode casefold contract", () => {
    expect(PYTHON_CASEFOLD_UNICODE_VERSION).toBe("13.0.0");
    expect(
      [
        "Straße",
        "MICRO µ",
        "ſ",
        "ǰ",
        "ﬃ",
        "ᾷ",
        "ꭰ",
        "İ",
        "Straße—Threshold_case",
        "ὖ",
        "ẞ",
        "Σςσ",
        "A𞊐B",
      ].map(normalizeSearchText),
    ).toEqual([
      "strasse",
      "micro μ",
      "s",
      "j",
      "ffi",
      "α ι",
      "Ꭰ",
      "i",
      "strasse threshold case",
      "υ",
      "ss",
      "σσσ",
      "a b",
    ]);
  });

  test("maps scalar folds back to exact original UTF-16 spans", () => {
    expect(normalizedSearchTokenSpans("𐺀 Straße ᾷ")).toEqual([
      { normalized: "𐺀", start: 0, end: 2 },
      { normalized: "strasse", start: 3, end: 9 },
      { normalized: "α", start: 10, end: 11 },
      { normalized: "ι", start: 10, end: 11 },
    ]);
  });

  test("waits for one normalized token with at least three characters", () => {
    expect(searchHasIndexableToken("a")).toBeFalse();
    expect(searchHasIndexableToken("GL")).toBeFalse();
    expect(searchHasIndexableToken("x GLD")).toBeTrue();
    expect(searchHasIndexableToken("ßß")).toBeTrue();
  });
});
