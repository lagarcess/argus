import { expect, test } from "bun:test";
import { isGuestSimulationConversionRejection } from "../lib/guest-conversion-recovery";

test("recognizes only authoritative guest run conversion rejections", () => {
  expect(
    isGuestSimulationConversionRejection("account_conversion_required", {
      type: "run_backtest",
      id: "run",
      label: "Run",
      value: "run",
    }),
  ).toBe(true);
  expect(
    isGuestSimulationConversionRejection("account_conversion_required", undefined),
  ).toBe(false);
});
