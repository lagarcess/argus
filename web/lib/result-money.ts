import displayPolicy from "../argus_display_contract/result_display_policy.json";

/**
 * How a result's money reads. The backend decides the digits once per run and
 * stores them on the result card as `currency_fraction_digits`
 * (src/argus/domain/result_money.py); every reader takes that stored value and
 * rounds half up. A card stored before the decision reads the policy default.
 */
export function resultCurrencyFractionDigits(stored: unknown): number {
  return typeof stored === "number" &&
    Number.isInteger(stored) &&
    stored >= 0 &&
    stored <= 2
    ? stored
    : displayPolicy.currency_fraction_digits;
}

export function resultMoneyFormatOptions(stored: unknown) {
  const digits = resultCurrencyFractionDigits(stored);
  return {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    roundingMode: displayPolicy.currency_rounding_mode as "halfExpand",
  };
}
