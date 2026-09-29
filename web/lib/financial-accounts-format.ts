import type { FinancialAccountNature } from "./financial-accounts-api";

export class AccountAmountInputError extends Error {
  readonly code = "amount_invalid";

  constructor() {
    super("Enter a complete amount using the displayed separators.");
    this.name = "AccountAmountInputError";
  }
}

function decimalParts(amount: string): RegExpMatchArray {
  const parts = amount.match(/^(-?)([0-9]+)(?:\.([0-9]+))?$/);
  if (!parts) throw new AccountAmountInputError();
  return parts;
}

function numberFormatter(locale: string): Intl.NumberFormat {
  return new Intl.NumberFormat(locale, {
    useGrouping: "always",
    maximumFractionDigits: 0,
  });
}

function separators(locale: string): { decimal: string; group: string | undefined } {
  const parts = new Intl.NumberFormat(locale).formatToParts(1234567.8);
  return {
    decimal: parts.find((part) => part.type === "decimal")?.value ?? ".",
    group: parts.find((part) => part.type === "group")?.value,
  };
}

/** Currency labels and separators change; the server's digits never do. */
export function formatAccountAmount(amount: string, currency: string, locale: string): string {
  const [, sign, whole, fraction] = decimalParts(amount);
  const integer = numberFormatter(locale).format(BigInt(whole));
  const decimal = fraction === undefined ? "" : `${separators(locale).decimal}${fraction}`;
  const pattern = new Intl.NumberFormat(locale, {
    style: "currency", currency, currencyDisplay: "code",
    minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).formatToParts(BigInt(sign === "-" ? -1 : 1));
  return pattern.map((part) => part.type === "integer" ? `${integer}${decimal}` : part.value).join("");
}

/** Normalize valid locale syntax only. Currency precision and range stay server-owned. */
export function parseAccountAmountInput(text: string, locale: string): string {
  const trimmed = text.trim();
  const sign = trimmed.startsWith("-") ? "-" : "";
  const unsigned = sign ? trimmed.slice(1) : trimmed;
  const { decimal, group } = separators(locale);
  const pieces = unsigned.split(decimal);
  if (pieces.length > 2) throw new AccountAmountInputError();
  const [whole, fraction] = pieces;
  const digits = group ? whole.split(group).join("") : whole;
  if (!/^[0-9]+$/.test(digits) || (fraction !== undefined && !/^[0-9]+$/.test(fraction))) {
    throw new AccountAmountInputError();
  }
  if (group && whole.includes(group) && numberFormatter(locale).format(BigInt(digits)) !== whole) {
    throw new AccountAmountInputError();
  }
  return `${sign}${digits}${fraction === undefined ? "" : `.${fraction}`}`;
}

/** Read values are owner-signed; liability forms ask for the amount owed. */
export function liabilityAmountInput(amount: string, nature: FinancialAccountNature): string {
  decimalParts(amount);
  if (nature !== "liability") return amount;
  if (/^-?0+(?:\.0+)?$/.test(amount)) return amount.replace(/^-/, "");
  return amount.startsWith("-") ? amount.slice(1) : `-${amount}`;
}

export function formatAccountDate(instant: string, zone: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: zone }).format(new Date(instant));
}
