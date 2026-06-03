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
    content,
    actions: retryAction ? [retryAction] : undefined,
  };
}
