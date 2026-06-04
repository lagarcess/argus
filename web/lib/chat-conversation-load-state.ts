import type { Message } from "@/components/chat/types";
import { conversationLoadRetryActionFromConversationId } from "./chat-retry-actions";

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
    actions: retryAction ? [retryAction] : undefined,
  };
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
