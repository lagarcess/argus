import { describe, expect, test } from "bun:test";

import {
  costEditDraftFromDisplayFacts,
  costEditDraftToRates,
  decimalRateToPercentInput,
  isValidCostEditDraft,
  isValidFeePercent,
  isValidSlippagePercent,
  parseCostPercentInput,
} from "../lib/confirmation-cost-edit";

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

  test("converts a valid percent draft to the endpoint's decimal rates", () => {
    expect(
      costEditDraftToRates({ feePercent: "0.2", slippagePercent: "0.1" }),
    ).toEqual({ fee_rate: 0.002, slippage: 0.001 });
    expect(costEditDraftToRates({ feePercent: "0", slippagePercent: "0" })).toEqual(
      { fee_rate: 0, slippage: 0 },
    );
  });

  test("refuses to convert invalid drafts", () => {
    expect(
      costEditDraftToRates({ feePercent: "-1", slippagePercent: "0" }),
    ).toBeNull();
    expect(
      costEditDraftToRates({ feePercent: "0.1", slippagePercent: "9" }),
    ).toBeNull();
    expect(
      isValidCostEditDraft({ feePercent: "0.1", slippagePercent: "0.05" }),
    ).toBe(true);
    expect(isValidCostEditDraft({ feePercent: "", slippagePercent: "0" })).toBe(
      false,
    );
  });
});
