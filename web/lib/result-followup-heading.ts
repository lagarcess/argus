/**
 * Typed heading key for latest-result fact answers.
 *
 * The backend no longer bakes markdown headings into fact-answer prose; it
 * emits a typed `response_intent` whose facts carry the canonical fact key.
 * The frontend owns the heading chrome: it localizes the key via i18n and
 * silently renders nothing when a key has no translation.
 */

const FACT_HEADING_INTENT_KINDS = new Set([
  "beginner_guidance",
  "unsupported_recovery",
]);

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/**
 * Works on both delivery shapes: the live stream's final payload (fields at
 * top level) and a persisted message's metadata — both carry
 * `response_intent`.
 */
export function resultFactHeadingKeyFromMetadata(
  metadata: Record<string, unknown>,
): string | null {
  const responseIntent = recordOrNull(metadata.response_intent);
  if (!responseIntent) return null;
  const kind = stringOrNull(responseIntent.kind);
  if (!kind || !FACT_HEADING_INTENT_KINDS.has(kind)) return null;
  const facts = recordOrNull(responseIntent.facts);
  if (!facts) return null;
  return stringOrNull(facts.fact_key) ?? stringOrNull(facts.requested_metric);
}
