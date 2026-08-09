import type { Message } from "@/components/chat/types";

/**
 * The confirmation a peer add or undo applies to: the newest card still
 * active in the transcript.
 *
 * Pure over the messages it is given, because the undo toast's handler
 * outlives the render that created it; the caller passes current messages
 * from a ref so a stale closure can never patch the wrong card.
 */
export function activeConfirmationIdFrom(messages: Message[]): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const candidate = messages[index]?.confirmation;
    if (!candidate) continue;
    if (
      candidate.confirmation_state === "active" ||
      !candidate.confirmation_state
    ) {
      return candidate.confirmation_id ?? null;
    }
  }
  return null;
}
