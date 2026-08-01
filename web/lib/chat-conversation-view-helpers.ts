import type { HistoryItem } from "./argus-api";

export const COLD_TRANSCRIPT_RETRIEVAL_DELAY_MS = 150;
export const POST_TURN_TITLE_REFRESH_DELAYS_MS = [0, 1500, 5000, 9000, 13000];

export function historyItemBelongsToConversation(
  item: HistoryItem,
  targetConversationId: string,
) {
  return (
    item.id === targetConversationId ||
    item.conversation_id === targetConversationId
  );
}

export function isMissingConversationLoadError(error: unknown) {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const status = "status" in error ? Number(error.status) : null;
  const code =
    "code" in error && typeof error.code === "string" ? error.code : null;
  return status === 403 || status === 404 || code === "not_found";
}
