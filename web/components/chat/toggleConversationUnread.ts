import type { UseConversationActivityResult } from "./useConversationActivity";

type ConversationUnreadController = Pick<
  UseConversationActivityResult,
  | "hasEffectiveUnread"
  | "isMutationPending"
  | "markRead"
  | "markUnread"
  | "selectAttentionCursor"
>;

export function toggleConversationUnread(
  activity: ConversationUnreadController,
  conversationId: string | null,
): Promise<void> {
  if (!conversationId) return Promise.resolve();
  const isUnread = activity.hasEffectiveUnread(conversationId);
  const action = isUnread ? "mark_read" : "mark_unread";
  if (activity.isMutationPending(conversationId, action)) {
    return Promise.resolve();
  }
  return isUnread
    ? activity.markRead(
        conversationId,
        activity.selectAttentionCursor(conversationId),
      )
    : activity.markUnread(conversationId);
}
