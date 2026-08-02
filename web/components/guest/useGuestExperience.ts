"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MutableRefObject,
} from "react";
import type {
  ChatActionOption,
  ChatMention,
  Message,
} from "@/components/chat/types";
import type { StarterSelectionMetadata } from "@/components/chat/StarterActions";
import { useGuestConversion } from "@/components/guest/useGuestConversion";
import { useGuestShellActions } from "@/components/guest/useGuestShellActions";
import { getUsageAllowances } from "@/lib/argus-api";
import {
  decideGuestMessageGate,
  decideGuestSimulationGate,
  isExactGuestRunReplay,
} from "@/lib/guest-capability-gates";
import { replaceGuestConversation } from "@/lib/guest-api";
import { captureGuestFunnelEvent } from "@/lib/guest-analytics";
import type { UserResponse } from "@/lib/guest-account";
import { startGuestSession } from "@/lib/guest-session";
import { normalizeEnabledLanguage } from "@/lib/language-features";
import {
  latestDecisionResumeMessageId,
  newConversationConversionMode,
  type GuestPendingAction,
} from "@/lib/guest-conversion";

export type GuestResumeSend = (
  text: string,
  mentionsOrAction?: ChatMention[] | ChatActionOption,
  action?: ChatActionOption,
  options?: { bypassGuestGate?: boolean },
) => Promise<boolean>;

export function useGuestSendBridge(
  sendRef: MutableRefObject<GuestResumeSend | null>,
  send: GuestResumeSend,
) {
  useEffect(() => {
    sendRef.current = send;
    return () => {
      sendRef.current = null;
    };
  }, [send, sendRef]);
}

type UseGuestExperienceInput = {
  account: UserResponse | null;
  guestBootstrapRequired: boolean;
  conversationId: string | null;
  messages: Message[];
  sendRef: MutableRefObject<GuestResumeSend | null>;
  refreshAccount: () => Promise<UserResponse | null>;
  refreshHistory: () => void;
  closeTransientSidebar: () => void;
  startNewChat: () => Promise<unknown>;
  onOpenFeedback: () => void;
  onOpenOmnisearch: () => void;
  onRequestPendingGuestSignIn: () => void;
  onAdoptConversation: (conversationId: string) => void;
  onGuestBootstrapExpired: (publicAccountAccessEnabled: boolean) => void;
  onGuestBootstrapError: () => void;
  onGateError: () => void;
  onStartOverError: () => void;
  omnisearchShortcutEnabled: boolean;
};

type GuestSendAdmissionInput = {
  text: string;
  mentions: ChatMention[];
  action?: ChatActionOption;
  starterSelection?: StarterSelectionMetadata;
  language?: string | null;
};

export function useGuestExperience({
  account,
  guestBootstrapRequired,
  conversationId,
  messages,
  sendRef,
  refreshAccount,
  refreshHistory,
  closeTransientSidebar,
  startNewChat,
  onOpenFeedback,
  onOpenOmnisearch,
  onRequestPendingGuestSignIn,
  onAdoptConversation,
  onGuestBootstrapExpired,
  onGuestBootstrapError,
  onGateError,
  onStartOverError,
  omnisearchShortcutEnabled,
}: UseGuestExperienceInput) {
  const [isNewConversationOpen, setIsNewConversationOpen] = useState(false);
  const [isReplacingConversation, setIsReplacingConversation] = useState(false);
  const [resumeDecisionArtifactId, setResumeDecisionArtifactId] =
    useState<string | null>(null);
  const pendingGuestAdmissionRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      pendingGuestAdmissionRef.current?.abort();
      pendingGuestAdmissionRef.current = null;
    },
    [],
  );

  const resumeGuestAction = useCallback(
    async (action: GuestPendingAction) => {
      if (action.reason === "message_limit") {
        await sendRef.current?.(action.text, action.mentions, undefined, {
          bypassGuestGate: true,
        });
      } else if (action.reason === "second_simulation") {
        await sendRef.current?.(
          action.action.label || action.action.value || "",
          {
            ...action.action,
            payload: {
              ...action.action.payload,
              idempotency_key: action.actionId,
            },
          },
          undefined,
          { bypassGuestGate: true },
        );
      } else if (action.reason === "save_decision") {
        setResumeDecisionArtifactId(action.artifactId);
      } else if (action.reason === "new_conversation") {
        await startNewChat();
      }
      refreshHistory();
    },
    [refreshHistory, sendRef, startNewChat],
  );

  const conversion = useGuestConversion({
    account,
    conversationId,
    refreshAccount,
    onResume: resumeGuestAction,
  });

  const shell = useGuestShellActions({
    account,
    guestBootstrapRequired,
    hasAcceptedContent: messages.some((message) => message.role === "user"),
    closeTransientSidebar,
    onOpenFeedback,
    onNewChat: startNewChat,
    onRequestNonEmptyGuestChoice: () => setIsNewConversationOpen(true),
    onRequestGuestDecision: (artifactId) => {
      if (!conversationId) return;
      conversion.requestConversion("save_decision", {
        reason: "save_decision",
        conversationId,
        actionId: crypto.randomUUID(),
        artifactId,
      });
    },
    onOpenOmnisearch,
    onRequestSignIn: () => {
      if (guestBootstrapRequired) {
        pendingGuestAdmissionRef.current?.abort();
        pendingGuestAdmissionRef.current = null;
        onRequestPendingGuestSignIn();
        return;
      }
      conversion.requestConversion(
        "keep_history",
        conversationId
          ? {
              reason: "keep_history",
              conversationId,
              actionId: crypto.randomUUID(),
            }
          : null,
      );
    },
    omnisearchShortcutEnabled,
  });

  const admitSend = useCallback(
    async ({
      text,
      mentions,
      action,
      starterSelection,
      language,
    }: GuestSendAdmissionInput) => {
      const admissionController = guestBootstrapRequired
        ? new AbortController()
        : null;
      const admissionCancelled = () =>
        admissionController?.signal.aborted ?? false;
      if (admissionController) {
        pendingGuestAdmissionRef.current?.abort();
        pendingGuestAdmissionRef.current = admissionController;
      }

      try {
        let effectiveAccount = account;
        if (guestBootstrapRequired) {
          try {
            const bootstrap = await startGuestSession(language);
            if (admissionCancelled()) return false;
            if (bootstrap.renewed_after_expiry) {
              onGuestBootstrapExpired(
                bootstrap.public_account_access_enabled ?? false,
              );
              return false;
            }
            const refreshedAccount = await refreshAccount();
            if (admissionCancelled()) return false;
            if (refreshedAccount === null) {
              onGuestBootstrapError();
              return false;
            }
            effectiveAccount = refreshedAccount;
          } catch {
            if (!admissionCancelled()) onGuestBootstrapError();
            return false;
          }
        }
        if (admissionCancelled()) return false;
        if (effectiveAccount?.account_kind !== "guest") return true;

        if (starterSelection) {
          captureGuestFunnelEvent({
            event: "starter_action_selected",
            language: normalizeEnabledLanguage(language),
            surface: "starter_actions",
            strategy_category: starterSelection.strategy_category,
            terminal_outcome: "selected",
          });
        }

        try {
          const usage = await getUsageAllowances();
          if (admissionCancelled()) return false;
          if (action?.type === "run_backtest") {
            const decision = decideGuestSimulationGate({
              accountKind: "guest",
              availableNow: usage.allowances.backtests.available_now,
              exactReplay: isExactGuestRunReplay(messages, action),
            });
            if (decision.kind === "convert") {
              if (!conversationId) return false;
              conversion.requestConversion(
                decision.reason,
                {
                  reason: "second_simulation",
                  conversationId,
                  actionId: crypto.randomUUID(),
                  action,
                },
                "signup",
                usage.allowances.backtests.day?.period_end ?? null,
              );
              return false;
            }
          } else if (!action?.type) {
            const decision = decideGuestMessageGate({
              accountKind: "guest",
              availableNow: usage.allowances.messages.available_now,
            });
            if (decision.kind === "convert") {
              if (!conversationId) return false;
              conversion.requestConversion(decision.reason, {
                reason: "message_limit",
                conversationId,
                actionId: crypto.randomUUID(),
                text,
                mentions,
              });
              return false;
            }
          }
          return true;
        } catch {
          if (!admissionCancelled()) onGateError();
          return false;
        }
      } finally {
        if (pendingGuestAdmissionRef.current === admissionController) {
          pendingGuestAdmissionRef.current = null;
        }
      }
    },
    [
      conversationId,
      conversion,
      account,
      guestBootstrapRequired,
      messages,
      onGuestBootstrapError,
      onGuestBootstrapExpired,
      onGateError,
      refreshAccount,
    ],
  );

  const startOver = useCallback(async () => {
    if (isReplacingConversation) return;
    setIsReplacingConversation(true);
    try {
      const { conversation } = await replaceGuestConversation();
      onAdoptConversation(conversation.id);
      setIsNewConversationOpen(false);
      refreshHistory();
    } catch {
      onStartOverError();
    } finally {
      setIsReplacingConversation(false);
    }
  }, [
    isReplacingConversation,
    onAdoptConversation,
    onStartOverError,
    refreshHistory,
  ]);

  const closeNewConversation = useCallback(() => {
    if (!isReplacingConversation) setIsNewConversationOpen(false);
  }, [isReplacingConversation]);

  const convertForNewConversation = useCallback(() => {
    if (!conversationId) return;
    setIsNewConversationOpen(false);
    conversion.requestConversion(
      "new_conversation",
      {
        reason: "new_conversation",
        conversationId,
        actionId: crypto.randomUUID(),
      },
      newConversationConversionMode(
        conversion.publicAccountAccessEnabled,
      ),
    );
  }, [conversationId, conversion]);

  const clearResumeDecision = useCallback(
    () => setResumeDecisionArtifactId(null),
    [],
  );
  const resumeDecisionMessageId = latestDecisionResumeMessageId(
    messages,
    resumeDecisionArtifactId,
  );

  const requestGuestSearchUpgrade = useCallback(
    () => conversion.requestConversion("discovery_searches", null),
    [conversion],
  )

  return {
    ...shell,
    admitSend,
    requestGuestSearchUpgrade,
    resumeDecisionArtifactId,
    resumeDecisionMessageId,
    clearResumeDecision,
    conversion,
    newConversation: {
      isOpen: isNewConversationOpen,
      isReplacing: isReplacingConversation,
      close: closeNewConversation,
      startOver,
      convert: convertForNewConversation,
    },
  };
}

export type GuestExperience = ReturnType<typeof useGuestExperience>;
