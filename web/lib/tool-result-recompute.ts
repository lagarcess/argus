import { recomputeToolResult } from "./argus-api";
import { applyToolResultMessage, type ToolResultCard, type ToolScalar } from "./tool-result-card";
import type { Message } from "@/components/chat/types";

export function toolRecomputeEligible(messageId: string, latestMessageId: string | null | undefined, busy: boolean): boolean {
  return messageId === latestMessageId && !busy;
}

/** A no-turn edit stays owned by the conversation and artifact that initiated it. */
export function toolResultRecomputeHandler(
  context: () => {
    source: () => { conversationId: string | null; latestMessageId: string | undefined; busy: boolean };
    setMessages: (update: (messages: Message[]) => Message[]) => void;
    invalidate: (conversationId: string) => void;
    reload: (conversationId: string) => Promise<unknown>;
  },
) {
  return async (messageId: string, card: ToolResultCard, changes: Record<string, ToolScalar>): Promise<void> => {
    const { source, setMessages, invalidate, reload } = context();
    const { conversationId: owner, latestMessageId, busy } = source();
    if (!owner || !toolRecomputeEligible(messageId, latestMessageId, busy)) return;
    try {
      const response = await recomputeToolResult(owner, messageId, card, changes);
      if (source().conversationId === owner) setMessages((current) => applyToolResultMessage(current, response));
      invalidate(owner);
    } catch (error) {
      if ((error as { status?: number }).status === 409 && source().conversationId === owner) void reload(owner);
      throw error;
    }
  };
}
