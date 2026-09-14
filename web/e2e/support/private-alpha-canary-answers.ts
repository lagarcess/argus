import {
  researchDegradedCodeFromMetadata,
  researchSourcesFromMetadata,
} from "../../lib/chat-discovery-sidecar";
import { retryableAssistantRecoveryCode } from "../../lib/chat-recovery-display";

// The canary judges a persisted answer with the projections the chat renders
// from, so an answer the reader sees as a failure never passes a check.

type JsonRecord = Record<string, unknown>;

function record(value: unknown): JsonRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

/** The newest assistant message on a messages API page, or null. */
export function latestAssistantMessage(payload: unknown): JsonRecord | null {
  const items = record(payload)?.items;
  const assistants = (Array.isArray(items) ? items : [])
    .map(record)
    .filter((item): item is JsonRecord => item?.role === "assistant");
  assistants.sort((left, right) =>
    String(left.created_at ?? "").localeCompare(String(right.created_at ?? "")),
  );
  return assistants[assistants.length - 1] ?? null;
}

/** Why a persisted assistant message is not an ordinary answer, or null. */
export function ordinaryAnswerFailure(message: unknown): string | null {
  const item = record(message);
  if (item?.role !== "assistant") return "assistant_answer_missing";
  const metadata = record(item.metadata) ?? {};
  const recoveryCode = retryableAssistantRecoveryCode(metadata.recovery);
  if (recoveryCode) return `assistant_answer_recovery_${recoveryCode}`;
  if (metadata.retry_last_turn) return "assistant_answer_offered_retry";
  if (typeof item.content !== "string" || !item.content.trim()) {
    return "assistant_answer_empty";
  }
  return null;
}

/** Why a persisted research turn is not a published answer with sources, or null. */
export function researchAnswerFailure(message: unknown): string | null {
  const answerFailure = ordinaryAnswerFailure(message);
  if (answerFailure) return answerFailure;
  const metadata = record(record(message)?.metadata) ?? {};
  const degradedCode = researchDegradedCodeFromMetadata(metadata);
  if (degradedCode) return `research_answer_degraded_${degradedCode}`;
  return researchSourcesFromMetadata(metadata).length > 0
    ? null
    : "research_sources_missing";
}
