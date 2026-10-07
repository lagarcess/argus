import { describe, expect, test } from "bun:test";
import { normalizeAmount } from "../components/business-app/business-format";

describe("Record expense amount", () => {
  test("a single decimal comma becomes a dot", () => {
    expect(normalizeAmount(" 12,50 ")).toBe("12.50");
  });

  test("every other shape reaches the backend as typed", () => {
    expect(normalizeAmount("12.50")).toBe("12.50");
    expect(normalizeAmount("1,000.50")).toBe("1,000.50");
    expect(normalizeAmount("1,000,000")).toBe("1,000,000");
    expect(normalizeAmount("12.345")).toBe("12.345");
  });
});
