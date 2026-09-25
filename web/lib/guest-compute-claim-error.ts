import type { ChatActionOption } from "@/components/chat/types";
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
