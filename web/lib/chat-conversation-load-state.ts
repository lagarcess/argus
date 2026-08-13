import type { Message } from "@/components/chat/types";
import { conversationLoadRetryActionFromConversationId } from "./chat-retry-actions";

/** Profile-unreachable fallback: one synthetic assistant message wearing the
 * retryable failure treatment, with product copy owned by the caller. */
export function offlineFallbackMessage(content: string): Message {
  return {
    id: "offline",
    role: "ai",
    kind: "text",
    content,
    assistantRecoveryCode: "profile_unreachable",
  };
}

export function conversationLoadFailureMessage(
  conversationId: string,
  content: string,
): Message {
  const retryAction = conversationLoadRetryActionFromConversationId(conversationId);
  return {
    id: "conversation-load-failed",
    role: "ai",
    kind: "text",
    contentPresentation: "conversation_load_failure",
    content,
    // Transport-level load failure is a retryable infrastructure failure;
    // the code makes it wear the failure treatment instead of plain prose.
    assistantRecoveryCode: "conversation_load_failure",
    actions: retryAction ? [retryAction] : undefined,
  };
}

type EmptyChatSurfaceState = Readonly<{
  messages: readonly Message[];
  isHydratingConversation: boolean;
  hasConversationLoadFailure: boolean;
}>;

/**
 * A settled conversation with no messages is the account's landing surface.
 * Conversation identity is deliberately absent so every empty entry route
 * renders the same surface for the current account kind.
 */
export function shouldShowEmptyChatSurface({
  messages,
  isHydratingConversation,
  hasConversationLoadFailure,
}: EmptyChatSurfaceState): boolean {
  return (
    messages.length === 0 &&
    !isHydratingConversation &&
    !hasConversationLoadFailure
  );
}

export function shouldShowConversationDisclaimer(
  messages: Message[],
  isStreamingResponse: boolean,
) {
  return (
    isStreamingResponse ||
    messages.some(
      (message) => message.contentPresentation !== "conversation_load_failure",
    )
  );
}
