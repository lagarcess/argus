import type { ChatActionOption } from "@/components/chat/types";
import { retryLastTurnActionFromMessage } from "./chat-retry-actions";
import { parseRetryAfterSeconds } from "./retry-after";

export const GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE =
  "guest_compute_claim_unavailable";

export const GUEST_COMPUTE_CLAIM_MESSAGE_KEY =
  "chat.recovery.guest_compute_claim_unavailable";

export const GUEST_COMPUTE_CLAIM_RETRY_IN_KEY =
  "chat.recovery.guest_compute_claim_retry_in";

export function isGuestComputeClaimUnavailable(
  code: string | null | undefined,
): boolean {
  return code === GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE;
}

export function localizedGuestComputeClaimMessage(
  code: string | null | undefined,
  translate: (key: string) => string,
  fallback: string,
): string {
  if (!isGuestComputeClaimUnavailable(code)) {
    return fallback;
  }
  return translate(GUEST_COMPUTE_CLAIM_MESSAGE_KEY);
}

export function guestComputeClaimTransportPatch(input: {
  code: string | null | undefined;
  retryAfterHeader: string | null | undefined;
  retryAction: ChatActionOption | null;
  nowMs?: number;
}): {
  assistantRecoveryCode?: string;
  actions?: ChatActionOption[];
} {
  if (!isGuestComputeClaimUnavailable(input.code)) {
    return {};
  }
  const nowMs = input.nowMs ?? Date.now();
  const waitSeconds = parseRetryAfterSeconds(input.retryAfterHeader, nowMs);
  return {
    assistantRecoveryCode: GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
    actions: input.retryAction
      ? [
          {
            ...input.retryAction,
            availableAtMs: nowMs + waitSeconds * 1000,
          },
        ]
      : undefined,
  };
}

export function guestClaimErrorRetryAction(input: {
  code: string | null | undefined;
  retryAction: ChatActionOption | null;
  message: string;
  assistantMessageId: string;
  chatAction?: ChatActionOption | null;
}): ChatActionOption | null {
  if (!isGuestComputeClaimUnavailable(input.code)) {
    return input.retryAction;
  }
  return (
    input.retryAction ??
    retryLastTurnActionFromMessage(input.message, {
      assistantMessageId: input.assistantMessageId,
      chatAction: input.chatAction ?? undefined,
    })
  );
}

export function guestClaimErrorKeepsLocalTranscript(
  code: string | null | undefined,
): boolean {
  return isGuestComputeClaimUnavailable(code);
}

export function guestClaimErrorTerminalPayload(assistantMessageId: string): {
  message_id: string;
  recovery: { code: typeof GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE };
} {
  return {
    message_id: assistantMessageId,
    recovery: { code: GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE },
  };
}

export function guestClaimErrorMessagePatch(input: {
  code: string | null | undefined;
  retryAfterHeader: string | null | undefined;
  retryAction: ChatActionOption | null;
  message: string;
  assistantMessageId: string;
  chatAction?: ChatActionOption | null;
  nowMs?: number;
}) {
  return guestComputeClaimTransportPatch({
    code: input.code,
    retryAfterHeader: input.retryAfterHeader,
    retryAction: guestClaimErrorRetryAction(input),
    nowMs: input.nowMs,
  });
}

type ClaimTransportReadiness = {
  accept: (
    payload: ReturnType<typeof guestClaimErrorTerminalPayload>,
    identityAuthorized: boolean,
  ) => boolean;
  finish: (identityAuthorized: boolean) => boolean;
};

export function settleGuestClaimTransportReadiness(
  terminalReadiness: ClaimTransportReadiness,
  code: string | null | undefined,
  assistantMessageId: string,
  authorized: boolean,
): void {
  if (guestClaimErrorKeepsLocalTranscript(code)) {
    terminalReadiness.accept(
      guestClaimErrorTerminalPayload(assistantMessageId),
      authorized,
    );
  }
  terminalReadiness.finish(authorized);
}
