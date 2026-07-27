"use client";

import { useCallback, useRef, useState } from "react";
import type { AuthFormSubmission } from "@/components/auth/AuthForm";
import {
  createGuestHandoff,
  linkGuestIdentity,
} from "@/lib/guest-api";
import {
  loginWithEmail,
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

type UseGuestConversionInput = {
  account: UserResponse | null;
  conversationId: string | null;
  refreshAccount: () => Promise<UserResponse | null>;
  onResume: (action: GuestPendingAction) => void | Promise<void>;
};

export function useGuestConversion({
  account,
  conversationId,
  refreshAccount,
  onResume,
}: UseGuestConversionInput) {
  const [isOpen, setIsOpen] = useState(false);
  const [reason, setReason] =
    useState<GuestConversionReason>("keep_history");
  const [initialMode, setInitialMode] =
    useState<GuestConversionMode>("login");
  const latchRef = useRef<SingleUseGuestAction | null>(null);
  const handoffPreparedRef = useRef(false);

  const requestConversion = useCallback(
    (
      nextReason: GuestConversionReason,
      pendingAction?: GuestPendingAction | null,
      nextInitialMode: GuestConversionMode = "login",
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
        await linkGuestIdentity({
          email: submission.email,
          password: submission.password,
        });
      } else {
        if (conversationId && !handoffPreparedRef.current) {
          const pending = latch?.take();
          if (pending) {
            latchRef.current = new SingleUseGuestAction(pending);
          }
          await createGuestHandoff({
            destination_email: submission.email,
            source_conversation_id: conversationId,
            pending_action: pending
              ? pendingGuestActionSummary(pending)
              : {
                  reason: "keep_history",
                  conversation_id: conversationId,
                  action_id: crypto.randomUUID(),
                },
          });
          handoffPreparedRef.current = true;
        }

        const authenticated = await loginWithEmail({
          email: submission.email,
          password: submission.password,
        });
        if (handoffPreparedRef.current) {
          const claimed = authenticated.guest_claim;
          if (!claimed) {
            throw new Error("The temporary conversation could not be claimed.");
          }
          const expected = latchRef.current?.take();
          if (expected) {
            const claimedAction = claimed.pending_action;
            if (
              !claimedAction ||
              claimedAction.action_id !== expected.actionId ||
              claimedAction.conversation_id !== expected.conversationId ||
              claimedAction.reason !== expected.reason
            ) {
              throw new Error("The pending action could not be verified.");
            }
            latchRef.current = new SingleUseGuestAction(expected);
          }
        }
      }

      await refreshAccount();
      const actionLatch = latchRef.current;
      const action = actionLatch?.take() ?? null;
      setIsOpen(false);
      handoffPreparedRef.current = false;
      if (action) {
        await onResume(action);
      }
    },
    [conversationId, onResume, refreshAccount],
  );

  return {
    isOpen,
    reason,
    initialMode,
    publicAccountAccessEnabled:
      account?.public_account_access_enabled ?? false,
    requestConversion,
    close,
    authenticate,
  };
}
