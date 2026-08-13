"use client";

import { useCallback, useRef, useState } from "react";
import type { AuthFormSubmission } from "@/components/auth/AuthForm";
import {
  createGuestHandoff,
  registerGuestAccount,
} from "@/lib/guest-api";
import {
  loginWithEmail,
  normalizeApiLanguage,
  signupWithEmail,
} from "@/lib/argus-api";
import type { UserResponse } from "@/lib/guest-account";
import { captureGuestFunnelEvent } from "@/lib/guest-analytics";
import {
  pendingGuestActionSummary,
  SingleUseGuestAction,
  type GuestConversionMode,
  type GuestConversionReason,
  type GuestPendingAction,
} from "@/lib/guest-conversion";
import { randomId } from "@/lib/random-id";

type GuestClaim = {
  conversation_id: string;
  pending_action: {
    reason: string;
    conversation_id: string;
    action_id: string;
  } | null;
};

function verifiedClaimAction(
  claimed: GuestClaim,
  conversationId: string,
  latch: SingleUseGuestAction | null,
) {
  if (claimed.conversation_id !== conversationId) {
    throw new Error("The temporary conversation could not be verified.");
  }
  const expected = latch?.take() ?? null;
  if (!expected) return null;
  const claimedAction = claimed.pending_action;
  if (
    !claimedAction ||
    claimedAction.action_id !== expected.actionId ||
    claimedAction.conversation_id !== expected.conversationId ||
    claimedAction.reason !== expected.reason
  ) {
    throw new Error("The pending action could not be verified.");
  }
  return expected;
}

type UseGuestConversionInput = {
  account: UserResponse | null;
  conversationId: string | null;
  refreshAccount: () => Promise<UserResponse | null>;
  refreshHistory: () => void | Promise<unknown>;
  onResume: (action: GuestPendingAction) => void | Promise<void>;
};

export function useGuestConversion({
  account,
  conversationId,
  refreshAccount,
  refreshHistory,
  onResume,
}: UseGuestConversionInput) {
  const [isOpen, setIsOpen] = useState(false);
  const [reason, setReason] =
    useState<GuestConversionReason>("keep_history");
  const [initialMode, setInitialMode] =
    useState<GuestConversionMode>("login");
  const [resetAt, setResetAt] = useState<string | null>(null);
  const [resetKind, setResetKind] = useState<"daily" | "workspace">("daily");
  const latchRef = useRef<SingleUseGuestAction | null>(null);
  const handoffPreparedRef = useRef(false);
  const sourceConversationId =
    conversationId ?? account?.guest?.conversation_id ?? null;

  const requestConversion = useCallback(
    (
      nextReason: GuestConversionReason,
      pendingAction?: GuestPendingAction | null,
      nextInitialMode: GuestConversionMode = "login",
      nextResetAt: string | null = null,
      nextResetKind: "daily" | "workspace" = "daily",
    ) => {
      if (account?.account_kind === "guest") {
        captureGuestFunnelEvent({
          event: "conversion_prompt_shown",
          language: account.user.language,
          surface: "conversion_modal",
          conversion_reason: nextReason,
          terminal_outcome: "shown",
        });
      }
      setReason(nextReason);
      setInitialMode(nextInitialMode);
      setResetAt(nextResetAt);
      setResetKind(nextResetKind);
      latchRef.current = pendingAction
        ? new SingleUseGuestAction(pendingAction)
        : null;
      handoffPreparedRef.current = false;
      setIsOpen(true);
    },
    [account],
  );

  const close = useCallback(() => {
    setIsOpen(false);
    handoffPreparedRef.current = false;
  }, []);

  const authenticate = useCallback(
    async (submission: AuthFormSubmission) => {
      const latch = latchRef.current;
      if (submission.mode === "signup") {
        if (!sourceConversationId) {
          const registered = await signupWithEmail({
            email: submission.email,
            password: submission.password,
            language: normalizeApiLanguage(account?.user.language),
            display_name: submission.displayName || null,
          });
          if (registered.needsEmailConfirmation) {
            return { status: "email_confirmation_required" as const };
          }
        } else {
          const pending = latch?.take();
          if (pending) {
            latchRef.current = new SingleUseGuestAction(pending);
          }
          const registered = await registerGuestAccount({
            email: submission.email,
            password: submission.password,
            language: normalizeApiLanguage(account?.user.language),
            display_name: submission.displayName || null,
            source_conversation_id: sourceConversationId,
            pending_action: pending
              ? pendingGuestActionSummary(pending)
              : {
                  reason: "keep_history",
                  conversation_id: sourceConversationId,
                  action_id: randomId(),
                },
          });
          handoffPreparedRef.current = true;
          if (registered.needsEmailConfirmation) {
            return { status: "email_confirmation_required" as const };
          }
          const claimed = registered.response.guest_claim;
          if (!claimed) {
            throw new Error("The temporary conversation could not be claimed.");
          }
          const expected = verifiedClaimAction(
            claimed,
            sourceConversationId,
            latchRef.current,
          );
          if (expected) {
            latchRef.current = new SingleUseGuestAction(expected);
          }
        }
      } else {
        if (sourceConversationId && !handoffPreparedRef.current) {
          const pending = latch?.take();
          if (pending) {
            latchRef.current = new SingleUseGuestAction(pending);
          }
          await createGuestHandoff({
            destination_email: submission.email,
            source_conversation_id: sourceConversationId,
            pending_action: pending
              ? pendingGuestActionSummary(pending)
              : {
                  reason: "keep_history",
                  conversation_id: sourceConversationId,
                  action_id: randomId(),
                },
          });
          handoffPreparedRef.current = true;
        }

        const authenticated = await loginWithEmail({
          email: submission.email,
          password: submission.password,
        });
        if (handoffPreparedRef.current && sourceConversationId) {
          const claimed = authenticated.guest_claim;
          if (!claimed) {
            throw new Error("The temporary conversation could not be claimed.");
          }
          const expected = verifiedClaimAction(
            claimed,
            sourceConversationId,
            latchRef.current,
          );
          if (expected) {
            latchRef.current = new SingleUseGuestAction(expected);
          }
        }
      }

      await refreshAccount();
      // The handoff changes the durable owner in the same request path. Refresh
      // Recents before a pending follow-up can fail or navigate away, so the
      // account's canonical conversation projection is visible immediately.
      await refreshHistory();
      const actionLatch = latchRef.current;
      const action = actionLatch?.take() ?? null;
      setIsOpen(false);
      handoffPreparedRef.current = false;
      if (action) {
        await onResume(action);
      }
    },
    [
      account?.user.language,
      onResume,
      refreshAccount,
      refreshHistory,
      sourceConversationId,
    ],
  );

  return {
    isOpen,
    reason,
    initialMode,
    resetAt,
    resetKind,
    publicAccountAccessEnabled:
      account?.public_account_access_enabled ?? false,
    locale:
      account?.user.language === "es-419"
        ? ("es-419" as const)
        : ("en-US" as const),
    requestConversion,
    close,
    authenticate,
  };
}
