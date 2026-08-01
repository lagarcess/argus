"use client";

import { useCallback, useEffect } from "react";
import type { UserResponse } from "@/lib/guest-account";
import { decideGuestNewConversationGate } from "@/lib/guest-capability-gates";
import { matchesKeyboardShortcut } from "@/lib/keyboard-shortcuts";

type GuestShellActionsInput = {
  account: UserResponse | null;
  hasAcceptedContent: boolean;
  closeTransientSidebar: () => void;
  onOpenFeedback: () => void;
  onNewChat: () => void | Promise<unknown>;
  onRequestNonEmptyGuestChoice: () => void;
  onRequestGuestDecision: (artifactId: string) => void;
  onOpenOmnisearch: () => void;
  onRequestSignIn: () => void;
  omnisearchShortcutEnabled: boolean;
};

export function useGuestShellActions({
  account,
  hasAcceptedContent,
  closeTransientSidebar,
  onOpenFeedback,
  onNewChat,
  onRequestNonEmptyGuestChoice,
  onRequestGuestDecision,
  onOpenOmnisearch,
  onRequestSignIn,
  omnisearchShortcutEnabled,
}: GuestShellActionsInput) {
  const isGuest = account?.account_kind === "guest";
  const capabilities = account?.capabilities;
  const canManageConversation =
    capabilities?.can_manage_conversation ?? true;
  const canSaveDecision = capabilities?.can_save_decision ?? true;
  const canUseOmnisearch = capabilities?.can_use_omnisearch ?? true;
  const canUseGroundedDiscovery =
    capabilities?.can_use_grounded_discovery ?? true;

  const requestOmnisearch = useCallback(() => {
    if (isGuest && !canUseOmnisearch) return;
    onOpenOmnisearch();
  }, [canUseOmnisearch, isGuest, onOpenOmnisearch]);

  const requestGuestSignIn = useCallback(() => {
    onRequestSignIn();
  }, [onRequestSignIn]);

  const requestGuestDecision = useCallback(
    (artifactId: string) => onRequestGuestDecision(artifactId),
    [onRequestGuestDecision],
  );

  const requestGuestFeedback = useCallback(() => {
    onOpenFeedback();
  }, [onOpenFeedback]);

  const requestNewChat = useCallback(() => {
    const decision = decideGuestNewConversationGate({
      accountKind: isGuest ? "guest" : "registered",
      hasAcceptedContent,
    });
    if (decision.kind === "choose_non_empty") {
      onRequestNonEmptyGuestChoice();
    } else {
      void onNewChat();
    }
    closeTransientSidebar();
  }, [
    closeTransientSidebar,
    hasAcceptedContent,
    isGuest,
    onNewChat,
    onRequestNonEmptyGuestChoice,
  ]);

  useEffect(() => {
    if (!omnisearchShortcutEnabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (!matchesKeyboardShortcut("omnisearch", event)) {
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
    canUseGroundedDiscovery,
    requestGuestDecision,
    requestGuestFeedback,
    requestGuestSignIn,
    requestNewChat,
    requestOmnisearch,
  };
}
