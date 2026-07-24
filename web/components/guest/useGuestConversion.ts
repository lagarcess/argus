"use client";

import { useCallback, useRef, useState } from "react";
import type { AuthFormSubmission } from "@/components/auth/AuthForm";
import {
  claimGuestHandoff,
  createGuestHandoff,
  linkGuestIdentity,
  loginWithEmail,
} from "@/lib/argus-api";
import type { UserResponse } from "@/lib/guest-account";
import {
  pendingGuestActionSummary,
  SingleUseGuestAction,
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
  const latchRef = useRef<SingleUseGuestAction | null>(null);
  const handoffIdRef = useRef<string | null>(null);

  const requestConversion = useCallback(
    (
      nextReason: GuestConversionReason,
      pendingAction?: GuestPendingAction | null,
    ) => {
      setReason(nextReason);
      latchRef.current = pendingAction
        ? new SingleUseGuestAction(pendingAction)
        : null;
      handoffIdRef.current = null;
      setIsOpen(true);
    },
    [],
  );

  const close = useCallback(() => {
    setIsOpen(false);
    handoffIdRef.current = null;
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
        if (conversationId && !handoffIdRef.current) {
          const pending = latch?.take();
          if (pending) {
            latchRef.current = new SingleUseGuestAction(pending);
          }
          const handoff = await createGuestHandoff({
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
          handoffIdRef.current = handoff.handoff_id;
        }

        await loginWithEmail({
          email: submission.email,
          password: submission.password,
        });
        if (handoffIdRef.current) {
          const claimed = await claimGuestHandoff(handoffIdRef.current);
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
      handoffIdRef.current = null;
      if (action) {
        await onResume(action);
      }
    },
    [conversationId, onResume, refreshAccount],
  );

  return {
    isOpen,
    reason,
    publicAccountAccessEnabled:
      account?.public_account_access_enabled ?? false,
    requestConversion,
    close,
    authenticate,
  };
}
