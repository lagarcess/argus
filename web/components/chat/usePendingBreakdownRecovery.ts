import { useEffect, type Dispatch, type SetStateAction } from "react";
import type { ApiMessage } from "@/lib/argus-api";
import { conversationLoadFailureMessage } from "@/lib/chat-conversation-load-state";
import { loadAllConversationMessagePages, resolveOrdinaryTransportAmbiguityView } from "@/lib/chat-message-hydration";
import { hydrateMessagesFromApi } from "./chat-message-projection";
import type { Message } from "./types";

/** Reuse ordinary-turn readback, including its deadline and load-retry state. */
export function recoverPendingBreakdown(
  messages: Message[], pending: Message, load: () => Promise<ApiMessage[]>,
  loadErrorText: string,
  options: Parameters<typeof resolveOrdinaryTransportAmbiguityView>[5] = {},
) {
  const owner = pending.pendingBreakdown!;
  return resolveOrdinaryTransportAmbiguityView(load, hydrateMessagesFromApi,
    { assistantId: pending.id, message: conversationLoadFailureMessage(owner.conversationId, loadErrorText) },
    new Set(messages.filter((message) => message.id !== owner.turnId).map((message) => message.id)),
    owner.requestId, options,
  );
}

export function usePendingBreakdownRecovery(
  messages: Message[], conversationId: string | null,
  setMessages: Dispatch<SetStateAction<Message[]>>,
  loadErrorText: string, onSettled: (conversationId: string) => void,
) {
  useEffect(() => {
    const pending = messages.find((message) => message.pendingBreakdown?.conversationId === conversationId);
    if (!pending || !conversationId) return;
    const controller = new AbortController();
    void recoverPendingBreakdown(messages, pending,
      () => loadAllConversationMessagePages(conversationId, undefined, { signal: controller.signal }),
      loadErrorText, { signal: controller.signal },
    ).then((view) => {
      if (controller.signal.aborted) return;
      setMessages((current) => {
        if (!current.some((message) => message.id === pending.id)) return current;
        return typeof view.messages === "function" ? view.messages(current) : view.messages;
      });
      if (Array.isArray(view.messages)) onSettled(conversationId);
    });
    return () => controller.abort();
  }, [messages, conversationId, setMessages, loadErrorText, onSettled]);
}
