import handoff from "./private-alpha-canary-handoff.json";

// Canary reasons are published in logs and evidence. The handoff contract file
// owns their grammar (lowercase words and HTTP statuses), and the shell importer
// reads the same file.

export const REASON_CODE_PATTERN = new RegExp(handoff.reason.pattern);
export const REASON_CODE_MAX_LENGTH = handoff.reason.max_length;
export const UNRECOGNIZED_REASON = handoff.reason.unrecognized;

export function isReasonCode(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= REASON_CODE_MAX_LENGTH &&
    REASON_CODE_PATTERN.test(value)
  );
}

function reasonPart(part: string | number): string {
  const accepted =
    typeof part === "number"
      ? Number.isInteger(part) && isReasonCode(`http_${part}`)
      : isReasonCode(part);
  return accepted ? String(part) : "unrecognized";
}

/** A reason from literal and backend parts; a part the contract would refuse is unrecognized, never rewritten. */
export function reasonCode(...parts: Array<string | number>): string {
  const code = parts.map(reasonPart).join("_");
  return isReasonCode(code) ? code : UNRECOGNIZED_REASON;
}

/** A failure the canary's own code raised; only these reasons are ever published. */
export class CheckFailure extends Error {
  readonly reason: string;

  constructor(reason: string) {
    const safe = isReasonCode(reason) ? reason : UNRECOGNIZED_REASON;
    super(safe);
    this.reason = safe;
  }
}
