"use client";

import {
  useCallback,
  type Dispatch,
  type SetStateAction,
} from "react";
import { getMe, type HistoryItem } from "@/lib/argus-api";
import { privateAlphaOnboardingEnabled } from "@/lib/private-alpha-flags";

type UseChatSurfaceLifecycleInput = {
  conversationId: string | null;
  setHistoryItems: Dispatch<SetStateAction<HistoryItem[]>>;
  setShowOnboardingGoalCards: Dispatch<SetStateAction<boolean>>;
  resetToEmptyChatSurface: (conversationId?: string | null) => void;
  closeTransientSidebar: () => void;
  refreshHistory: () => void;
};

export function useChatSurfaceLifecycle({
  conversationId,
  setHistoryItems,
  setShowOnboardingGoalCards,
  resetToEmptyChatSurface,
  closeTransientSidebar,
  refreshHistory,
}: UseChatSurfaceLifecycleInput) {
  const startNewChat = useCallback(async () => {
    resetToEmptyChatSurface();
    closeTransientSidebar();
    try {
      const me = await getMe();
      const stage = me.user.onboarding.stage;
      setShowOnboardingGoalCards(
        me.account_kind !== "guest" &&
          privateAlphaOnboardingEnabled &&
          (stage === "language_selection" ||
            stage === "primary_goal_selection"),
      );
    } catch {
      setShowOnboardingGoalCards(false);
    }
    refreshHistory();
    return null;
  }, [
    closeTransientSidebar,
    refreshHistory,
    resetToEmptyChatSurface,
    setShowOnboardingGoalCards,
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
