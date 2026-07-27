"use client";

import {
  useCallback,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { HistoryItem } from "@/lib/argus-api";

type UseChatSurfaceLifecycleInput = {
  conversationId: string | null;
  setHistoryItems: Dispatch<SetStateAction<HistoryItem[]>>;
  resetToEmptyChatSurface: (conversationId?: string | null) => void;
  closeTransientSidebar: () => void;
  refreshHistory: () => void;
};

export function useChatSurfaceLifecycle({
  conversationId,
  setHistoryItems,
  resetToEmptyChatSurface,
  closeTransientSidebar,
  refreshHistory,
}: UseChatSurfaceLifecycleInput) {
  const startNewChat = useCallback(async () => {
    resetToEmptyChatSurface();
    closeTransientSidebar();
    refreshHistory();
    return null;
  }, [
    closeTransientSidebar,
    refreshHistory,
    resetToEmptyChatSurface,
  ]);

  const handleConversationRemoved = useCallback(
    (removedConversationId: string) => {
      setHistoryItems((current) =>
        current.filter(
          (item) =>
            !(
              item.id === removedConversationId ||
              item.conversation_id === removedConversationId
            ),
        ),
      );
      refreshHistory();
      if (removedConversationId === conversationId) {
        resetToEmptyChatSurface();
      }
    },
    [
      conversationId,
      refreshHistory,
      resetToEmptyChatSurface,
      setHistoryItems,
    ],
  );

  const handleAllConversationsDeleted = useCallback(() => {
    setHistoryItems([]);
    refreshHistory();
    if (conversationId !== null) resetToEmptyChatSurface();
  }, [
    conversationId,
    refreshHistory,
    resetToEmptyChatSurface,
    setHistoryItems,
  ]);

  return {
    startNewChat,
    adoptGuestConversation: resetToEmptyChatSurface,
    handleConversationRemoved,
    handleAllConversationsDeleted,
  };
}
