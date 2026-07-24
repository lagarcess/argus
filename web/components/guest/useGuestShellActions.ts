"use client";

import { useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { UserResponse } from "@/lib/guest-account";

type GuestShellActionsInput = {
  account: UserResponse | null;
  hasConversation: boolean;
  closeTransientSidebar: () => void;
  onOpenFeedback: () => void;
  onNewChat: () => void | Promise<unknown>;
  onOpenOmnisearch: () => void;
  omnisearchShortcutEnabled: boolean;
  showToast: (message: string) => void;
};

export function useGuestShellActions({
  account,
  hasConversation,
  closeTransientSidebar,
  onOpenFeedback,
  onNewChat,
  onOpenOmnisearch,
  omnisearchShortcutEnabled,
  showToast,
}: GuestShellActionsInput) {
  const { t } = useTranslation();
  const isGuest = account?.account_kind === "guest";
  const capabilities = account?.capabilities;
  const canManageConversation =
    capabilities?.can_manage_conversation ?? true;
  const canSaveDecision = capabilities?.can_save_decision ?? true;
  const canUseOmnisearch = capabilities?.can_use_omnisearch ?? true;

  const requestOmnisearch = useCallback(() => {
    if (isGuest && !canUseOmnisearch) {
      showToast(t("guest.shell.search_unavailable"));
      return;
    }
    onOpenOmnisearch();
  }, [canUseOmnisearch, isGuest, onOpenOmnisearch, showToast, t]);

  const requestGuestSignIn = useCallback(() => {
    showToast(t("guest.shell.sign_in_unavailable"));
  }, [showToast, t]);

  const requestGuestDecision = useCallback(() => {
    showToast(t("guest.shell.decision_unavailable"));
  }, [showToast, t]);

  const requestGuestFeedback = useCallback(() => {
    onOpenFeedback();
  }, [onOpenFeedback]);

  const requestNewChat = useCallback(() => {
    if (
      isGuest &&
      !capabilities?.can_create_additional_conversation &&
      hasConversation
    ) {
      showToast(t("guest.shell.new_chat_unavailable"));
      closeTransientSidebar();
      return;
    }
    void onNewChat();
  }, [
    capabilities?.can_create_additional_conversation,
    closeTransientSidebar,
    hasConversation,
    isGuest,
    onNewChat,
    showToast,
    t,
  ]);

  useEffect(() => {
    if (!omnisearchShortcutEnabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        !(event.metaKey || event.ctrlKey) ||
        event.key.toLowerCase() !== "k"
      ) {
        return;
      }
      event.preventDefault();
      requestOmnisearch();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [omnisearchShortcutEnabled, requestOmnisearch]);

  return {
    isGuest,
    canManageConversation,
    canSaveDecision,
    canUseOmnisearch,
    requestGuestDecision,
    requestGuestFeedback,
    requestGuestSignIn,
    requestNewChat,
    requestOmnisearch,
  };
}
