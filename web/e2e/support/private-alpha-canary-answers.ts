import { hydrateMessagesFromApi } from "../../components/chat/chat-message-projection";
import type { Message } from "../../components/chat/types";
import type { ApiMessage } from "../../lib/argus-api";
import { isRetryAction } from "../../lib/chat-retry-actions";

// The canary judges an answer by the message the chat renders from the saved
// transcript, so it passes only what a reader sees as an ordinary answer.

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
 * Why the chat would not render this message as an ordinary answer, or null.
 * Only the plain answer bubble passes: a card, a failure notice, a recovery
 * statement, or any other projected presentation is refused.
 */
export function ordinaryAnswerFailure(message: Message | null): string | null {
  if (!message || message.role !== "ai") return "assistant_answer_missing";
  if (message.kind !== "text") {
    return `assistant_answer_rendered_as_${message.kind}`;
  }
  if (message.assistantRecoveryCode) {
    return `assistant_answer_recovery_${message.assistantRecoveryCode}`;
  }
  if (message.recoveryDisplay) {
    return `assistant_answer_rendered_as_${message.recoveryDisplay.kind}`;
  }
  if (message.contentPresentation) {
    return `assistant_answer_rendered_as_${message.contentPresentation}`;
  }
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
    return `research_answer_degraded_${message.researchDegradedCode}`;
  }
  return message?.researchSources?.length ? null : "research_sources_missing";
}
