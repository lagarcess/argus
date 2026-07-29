import type { Conversation, HistoryItem } from "./argus-api";

export const RECENTS_INITIAL_GROUP_LIMIT = 5;

export type RecentChatGroupKey =
  | "pinned"
  | "today"
  | "yesterday"
  | "last_7_days"
  | "last_30_days"
  | "earlier";

export type RecentChatGroup = {
  key: RecentChatGroupKey;
  items: HistoryItem[];
  isPinned: boolean;
};

type ConversationProjectionOptions = Readonly<{
  guestExpiresAt?: string | null;
}>;

export function projectConversationToRecentChat(
  conversation: Conversation,
  options: ConversationProjectionOptions = {},
): HistoryItem {
  return {
    type: "chat",
    id: conversation.id,
    title: conversation.title,
    title_source: conversation.title_source,
    subtitle: conversation.last_message_preview ?? "No messages yet",
    pinned: conversation.pinned,
    created_at: conversation.updated_at,
    conversation_id: conversation.id,
    expires_at: options.guestExpiresAt ?? null,
  };
}

export function mergeRecentChats(
  existing: HistoryItem[],
  incoming: HistoryItem[],
): HistoryItem[] {
  const seen = new Set(
    existing.map((item) => item.conversation_id ?? item.id),
  );
  const merged = [...existing];
  for (const item of incoming) {
    const conversationId = item.conversation_id ?? item.id;
    if (seen.has(conversationId)) continue;
    seen.add(conversationId);
    merged.push(item);
  }
  return merged;
}

export function groupRecentChats(
  items: HistoryItem[],
  now = new Date(),
): RecentChatGroup[] {
  const groups: Record<RecentChatGroupKey, HistoryItem[]> = {
    pinned: [],
    today: [],
    yesterday: [],
    last_7_days: [],
    last_30_days: [],
    earlier: [],
  };
  const todayStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  ).getTime();
  const dayMs = 86_400_000;
  const yesterdayStart = todayStart - dayMs;
  const last7Start = todayStart - dayMs * 6;
  const last30Start = todayStart - dayMs * 29;

  for (const item of items) {
    if (item.pinned) {
      groups.pinned.push(item);
      continue;
    }
    const timestamp = new Date(item.created_at).getTime();
    if (timestamp >= todayStart) {
      groups.today.push(item);
    } else if (timestamp >= yesterdayStart) {
      groups.yesterday.push(item);
    } else if (timestamp >= last7Start) {
      groups.last_7_days.push(item);
    } else if (timestamp >= last30Start) {
      groups.last_30_days.push(item);
    } else {
      groups.earlier.push(item);
    }
  }

  return (
    [
      ["pinned", true],
      ["today", false],
      ["yesterday", false],
      ["last_7_days", false],
      ["last_30_days", false],
      ["earlier", false],
    ] as const
  )
    .filter(([key]) => groups[key].length > 0)
    .map(([key, isPinned]) => ({ key, items: groups[key], isPinned }));
}

export function getVisibleRecentChats(
  group: RecentChatGroup,
  options: Readonly<{
    expanded: boolean;
    selectedConversationId: string | null;
    limit?: number;
  }>,
): HistoryItem[] {
  const limit = options.limit ?? RECENTS_INITIAL_GROUP_LIMIT;
  if (group.isPinned || options.expanded || group.items.length <= limit) {
    return group.items;
  }

  const initialItems = group.items.slice(0, limit);
  if (
    !options.selectedConversationId ||
    initialItems.some(
      (item) =>
        (item.conversation_id ?? item.id) === options.selectedConversationId,
    )
  ) {
    return initialItems;
  }

  const selectedItem = group.items.find(
    (item) =>
      (item.conversation_id ?? item.id) === options.selectedConversationId,
  );
  if (!selectedItem) return initialItems;
  return [...initialItems.slice(0, Math.max(0, limit - 1)), selectedItem];
}
