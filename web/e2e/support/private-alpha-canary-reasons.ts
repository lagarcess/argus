// Canary reasons are published in logs and evidence, so a reason is built only
// from lowercase words and HTTP statuses and can never carry an identifier.

/** Words joined by underscores; the only numbers are HTTP statuses, 0 when none. */
export const REASON_CODE_PATTERN = /^[a-z]+(?:_(?:[a-z]+|0|[1-5][0-9]{2}))*$/;
export const REASON_CODE_MAX_LENGTH = 120;
export const UNRECOGNIZED_REASON = "reason_unrecognized";

const CODE_WORDS = /^[a-z]+(?:_[a-z]+)*$/;

export function isReasonCode(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= REASON_CODE_MAX_LENGTH &&
    REASON_CODE_PATTERN.test(value)
  );
}

function reasonPart(part: string | number): string {
  if (typeof part === "number") {
    const httpStatus =
      Number.isInteger(part) && (part === 0 || (part >= 100 && part <= 599));
    return httpStatus ? String(part) : "unrecognized";
  }
  return CODE_WORDS.test(part) ? part : "unrecognized";
}

/** A reason from literal and backend parts; any part that is not a code or HTTP status is unrecognized, never rewritten. */
export function reasonCode(...parts: Array<string | number>): string {
  const code = parts.map(reasonPart).join("_");
  return isReasonCode(code) ? code : UNRECOGNIZED_REASON;
}

/** A check failure whose reason is safe to publish in canary evidence. */
export class CheckFailure extends Error {
  readonly reason: string;

  constructor(reason: string) {
    const safe = isReasonCode(reason) ? reason : UNRECOGNIZED_REASON;
    super(safe);
    this.reason = safe;
  }
}
