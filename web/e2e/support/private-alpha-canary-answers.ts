import { hydrateMessagesFromApi } from "../../components/chat/chat-message-projection";
import type { Message } from "../../components/chat/types";
import type { ApiMessage } from "../../lib/argus-api";
import { isRetryAction } from "../../lib/chat-retry-actions";
import { reasonCode } from "./private-alpha-canary-reasons";

// The canary judges an answer by its two owners: the transcript projection says
// what the turn is, and the rendered message says what the chat announces.

/** Roles the chat gives every failure it presents inside a message. */
export const ANNOUNCEMENT_ROLES = ["status", "alert"] as const;
export const ANNOUNCEMENT_SELECTOR = ANNOUNCEMENT_ROLES.map(
  (role) => `[role="${role}"]`,
).join(", ");

/** The newest assistant message as the chat projects a messages API page. */
export function latestAssistantMessage(payload: unknown): Message | null {
  const items =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as { items?: unknown }).items
      : null;
  if (!Array.isArray(items)) return null;
  const answers = hydrateMessagesFromApi(items as ApiMessage[]).messages.filter(
    (message) => message.role === "ai",
  );
  return answers[answers.length - 1] ?? null;
}

/**
 * Why the projected turn is not an ordinary answer, or null. It reads what the
 * turn is (a text answer, a declared recovery, a retry offer); how the chat
 * presents the turn is judged from the rendered message's announcements.
 */
export function ordinaryAnswerFailure(message: Message | null): string | null {
  if (!message || message.role !== "ai") return "assistant_answer_missing";
  if (message.kind !== "text") {
    return reasonCode("assistant_answer_rendered_as", message.kind ?? "none");
  }
  const recovery =
    message.assistantRecoveryCode ?? message.recoveryDisplay?.kind;
  if (recovery) return reasonCode("assistant_answer_recovery", recovery);
  if (message.actions?.some(isRetryAction)) {
    return "assistant_answer_offered_retry";
  }
  if (!message.content?.trim()) return "assistant_answer_empty";
  return null;
}

/** Why a research turn is not a published answer with sources, or null. */
export function researchAnswerFailure(message: Message | null): string | null {
  const answerFailure = ordinaryAnswerFailure(message);
  if (answerFailure) return answerFailure;
  if (message?.researchDegradedCode) {
    return reasonCode("research_answer_degraded", message.researchDegradedCode);
  }
  return message?.researchSources?.length ? null : "research_sources_missing";
}
