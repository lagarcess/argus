"use client";

import { useCallback, useEffect } from "react";
import type { UserResponse } from "@/lib/guest-account";
import type { GuestDecisionResumeTarget } from "@/lib/guest-conversion";
import { decideGuestNewConversationGate } from "@/lib/guest-capability-gates";
import { hasOpenOverlay } from "@/components/layout/overlayStack";
import { matchesKeyboardShortcut } from "@/lib/keyboard-shortcuts";

type GuestShellActionsInput = {
  account: UserResponse | null;
  guestBootstrapRequired: boolean;
  hasAcceptedContent: boolean;
  closeTransientSidebar: () => void;
  onOpenFeedback: () => void;
  onNewChat: () => void | Promise<unknown>;
  onRequestNonEmptyGuestChoice: () => void;
  onRequestGuestDecision: (target: GuestDecisionResumeTarget) => void;
  onOpenOmnisearch: () => void;
  onRequestSignIn: () => void;
  omnisearchShortcutEnabled: boolean;
};

export function useGuestShellActions({
  account,
  guestBootstrapRequired,
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
  const isGuestPresentation = isGuest || guestBootstrapRequired;
  const capabilities = account?.capabilities;
  const registeredCapabilityFallback = account?.account_kind === "registered";
  const canManageConversation =
    capabilities?.can_manage_conversation ?? registeredCapabilityFallback;
  const canSaveDecision =
    capabilities?.can_save_decision ?? registeredCapabilityFallback;
  const canUseOmnisearch =
    capabilities?.can_use_omnisearch ?? registeredCapabilityFallback;
  const canUseGroundedDiscovery =
    capabilities?.can_use_grounded_discovery ?? registeredCapabilityFallback;
  const canSubmitFeedback = capabilities?.can_submit_feedback ?? false;

  const requestOmnisearch = useCallback(() => {
    if (isGuestPresentation && !canUseOmnisearch) return;
    onOpenOmnisearch();
  }, [canUseOmnisearch, isGuestPresentation, onOpenOmnisearch]);

  const requestGuestSignIn = useCallback(() => {
    onRequestSignIn();
  }, [onRequestSignIn]);

  const requestGuestDecision = useCallback(
    (target: GuestDecisionResumeTarget) => onRequestGuestDecision(target),
    [onRequestGuestDecision],
  );

  const requestGuestFeedback = useCallback(() => {
    if (!canSubmitFeedback) return;
    onOpenFeedback();
  }, [canSubmitFeedback, onOpenFeedback]);

  const requestNewChat = useCallback(() => {
    const decision = decideGuestNewConversationGate({
      accountKind: isGuestPresentation ? "guest" : "registered",
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
    isGuestPresentation,
    onNewChat,
    onRequestNonEmptyGuestChoice,
  ]);

  useEffect(() => {
    if (!omnisearchShortcutEnabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (!matchesKeyboardShortcut("omnisearch", event)) {
        return;
      }
      // Asked at press time, because the registry is the only thing that knows
      // what is open right now. Opening the palette over a dialog made it the
      // topmost layer at a lower z-index: invisible, but holding focus and the
      // keys meant for the surface the user could see.
      if (hasOpenOverlay()) {
        return;
      }
      event.preventDefault();
      requestOmnisearch();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [omnisearchShortcutEnabled, requestOmnisearch]);

  return {
    isGuest: isGuestPresentation,
    isEstablishedGuest: isGuest,
    canManageConversation,
    canSaveDecision,
    canUseOmnisearch,
    canUseGroundedDiscovery,
    canSubmitFeedback,
    requestGuestDecision,
    requestGuestFeedback,
    requestGuestSignIn,
    requestNewChat,
    requestOmnisearch,
  };
}
