import { describe, expect, test } from "bun:test";

import {
  costEditDraftFromDisplayFacts,
  decimalRateToPercentInput,
  executionCostEditMessage,
  isValidCostEditDraft,
  isValidFeePercent,
  isValidSlippagePercent,
  parseCostPercentInput,
} from "../lib/confirmation-cost-edit";

const t = (
  key: string,
  options?: string | { defaultValue?: string; fee?: string; slippage?: string },
) => {
  if (typeof options === "object" && options?.defaultValue) {
    return options.defaultValue
      .replace("{{fee}}", options.fee ?? "")
      .replace("{{slippage}}", options.slippage ?? "");
  }
  return typeof options === "string" ? options : key;
};

describe("confirmation cost edit helpers", () => {
  test("parses percent inputs with or without a percent sign", () => {
    expect(parseCostPercentInput("0.1")).toBe(0.1);
    expect(parseCostPercentInput(" 0.25% ")).toBe(0.25);
    expect(parseCostPercentInput("0")).toBe(0);
    expect(parseCostPercentInput("")).toBeNull();
    expect(parseCostPercentInput("abc")).toBeNull();
  });

  test("validates non-negative fees and capped slippage", () => {
    expect(isValidFeePercent(0)).toBe(true);
    expect(isValidFeePercent(0.5)).toBe(true);
    expect(isValidFeePercent(-0.1)).toBe(false);
    expect(isValidFeePercent(null)).toBe(false);
    expect(isValidSlippagePercent(0)).toBe(true);
    expect(isValidSlippagePercent(5)).toBe(true);
    expect(isValidSlippagePercent(5.1)).toBe(false);
    expect(isValidSlippagePercent(-1)).toBe(false);
  });

  test("prefills the editor from decimal display facts as percent strings", () => {
    expect(decimalRateToPercentInput(0.001)).toBe("0.1");
    expect(decimalRateToPercentInput(0.0005)).toBe("0.05");
    expect(decimalRateToPercentInput(0)).toBe("0");
    expect(decimalRateToPercentInput(null)).toBe("0");
    expect(
      costEditDraftFromDisplayFacts({ fees: 0.001, slippage: 0.0005 }),
    ).toEqual({ feePercent: "0.1", slippagePercent: "0.05" });
    expect(costEditDraftFromDisplayFacts(undefined)).toEqual({
      feePercent: "0",
      slippagePercent: "0",
    });
  });

  test("composes the canonical percent edit message once valid", () => {
    expect(
      executionCostEditMessage({ feePercent: "0.1", slippagePercent: "0.05" }, t),
    ).toBe("Set fees to 0.1% and slippage to 0.05% per trade.");
    expect(
      executionCostEditMessage({ feePercent: "0", slippagePercent: "0" }, t),
    ).toBe("Set fees to 0% and slippage to 0% per trade.");
  });

  test("refuses to compose a message for invalid drafts", () => {
    expect(
      executionCostEditMessage({ feePercent: "-1", slippagePercent: "0" }, t),
    ).toBeNull();
    expect(
      executionCostEditMessage({ feePercent: "0.1", slippagePercent: "9" }, t),
    ).toBeNull();
    expect(
      isValidCostEditDraft({ feePercent: "0.1", slippagePercent: "0.05" }),
    ).toBe(true);
    expect(isValidCostEditDraft({ feePercent: "", slippagePercent: "0" })).toBe(
      false,
    );
  });
});
