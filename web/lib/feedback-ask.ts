import type { Message } from "@/components/chat/types";
import { readStored, writeStored } from "./browser-storage";
import {
  feedbackContextForSubmission,
  type FeedbackRating,
} from "./feedback-context";

// Conversations whose ask has closed: answered, dismissed, or passed over by
// the next turn. The session set is truth; storage carries it across reloads.
const FEEDBACK_ASK_STORAGE_KEY = "argus:feedback-ask:v1" as const;
const closedThisSession = new Set<string>();

/** The one-tap answers, in the order the ask shows them. */
export const FEEDBACK_ASK_ANSWERS = [
  "negative",
  "neutral",
  "positive",
] as const satisfies readonly FeedbackRating[];

export const FEEDBACK_ASK_SOURCE = {
  source: "feedback_ask",
  surface: "chat",
} as const;

function readClosedIds(): Set<string> {
  try {
    const raw = readStored(FEEDBACK_ASK_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return new Set();
    return new Set(
      parsed.filter((item): item is string => typeof item === "string"),
    );
  } catch {
    return new Set();
  }
}

export function hasAskedForFeedback(conversationId: string): boolean {
  return (
    closedThisSession.has(conversationId) ||
    readClosedIds().has(conversationId)
  );
}

export function markAskedForFeedback(conversationId: string): void {
  closedThisSession.add(conversationId);
  const ids = readClosedIds();
  ids.add(conversationId);
  writeStored(FEEDBACK_ASK_STORAGE_KEY, JSON.stringify([...ids].sort()));
}

function isLandedResult(message: Message): boolean {
  if (message.role !== "ai") return false;
  if (message.kind === "strategy_result") {
    return Boolean(message.result) && !message.isLoadingResult;
  }
  return (
    message.toolResultCards?.some(
      (card) => card.outcome.status === "succeeded",
    ) ?? false
  );
}

/** A result card or a succeeded calculation arrived after the latest user message. */
export function resultLandedThisTurn(messages: readonly Message[]): boolean {
  const latestUser = messages.findLastIndex((message) => message.role === "user");
  return messages.slice(latestUser + 1).some(isLandedResult);
}

/** A tap carries no conversation identifiers; those travel only by choice. */
export function feedbackAskContext(rating: FeedbackRating) {
  return feedbackContextForSubmission(FEEDBACK_ASK_SOURCE, {
    includeConversationContext: false,
    rating,
    tags: [],
    attachmentCount: 0,
  });
}
