import type {
  HistoryItem,
  SearchConversationItem,
  SearchResponse,
} from "./argus-api";

const MAX_VISIBLE_RECENT_CONVERSATIONS = 50;

export type RecentRecallRequest = {
  q: "";
  limit: number;
  conversationIds?: string[];
  includeLedgerGroups: true;
};

type LoadRecentRecallParams = {
  recentItems: readonly HistoryItem[];
  fetchRecall: (params: RecentRecallRequest) => Promise<SearchResponse>;
  isCurrent?: () => boolean;
};

export type RecentRecallResponse = SearchResponse & {
  recentItems: HistoryItem[];
  recalledConversationIds: string[];
};

export function isRecentRecallResponse(
  response: SearchResponse,
): response is RecentRecallResponse {
  return (
    "recalledConversationIds" in response &&
    Array.isArray(response.recalledConversationIds)
  );
}

export function retainRecalledRecentItems(
  items: readonly HistoryItem[],
  recalledConversationIds: readonly string[],
): HistoryItem[] {
  const recalledIds = new Set(recalledConversationIds);
  return items.filter(
    (item) =>
      item.type === "chat" &&
      recalledIds.has(item.conversation_id ?? item.id),
  );
}

export async function loadCommandPaletteRecentRecall({
  recentItems,
  fetchRecall,
  isCurrent = () => true,
}: LoadRecentRecallParams): Promise<RecentRecallResponse | null> {
  const recentById = new Map<string, HistoryItem>();
  for (const item of recentItems) {
    if (item.type !== "chat") continue;
    const conversationId = item.conversation_id ?? item.id;
    if (conversationId && !recentById.has(conversationId)) {
      recentById.set(conversationId, item);
    }
  }
  const visibleIds = [...recentById.keys()];
  if (visibleIds.length > MAX_VISIBLE_RECENT_CONVERSATIONS) {
    throw new Error("Recent recall accepts at most 50 visible conversations.");
  }
  if (!visibleIds.length) {
    if (!isCurrent()) return null;
    const ledgerResponse = await fetchRecall({
      q: "",
      limit: 1,
      includeLedgerGroups: true,
    });
    if (!isCurrent()) return null;
    return {
      items: [],
      next_cursor: null,
      ledger_groups: ledgerResponse.ledger_groups ?? [],
      recentItems: [],
      recalledConversationIds: [],
    };
  }
  if (!isCurrent()) return null;

  const response = await fetchRecall({
    q: "",
    limit: visibleIds.length,
    conversationIds: visibleIds,
    includeLedgerGroups: true,
  });
  if (!isCurrent()) return null;

  const targetIds = new Set(visibleIds);
  const recalledById = new Map<string, SearchConversationItem>();
  for (const item of response.items) {
    if (
      item.type === "conversation" &&
      targetIds.has(item.conversation_id)
    ) {
      recalledById.set(item.conversation_id, item);
    }
  }
  const recalledConversationIds = visibleIds.filter((id) => recalledById.has(id));

  return {
    items: recalledConversationIds.map((id) => recalledById.get(id)!),
    next_cursor: null,
    ledger_groups: response.ledger_groups ?? [],
    recentItems: recalledConversationIds.map((id) => recentById.get(id)!),
    recalledConversationIds,
  };
}
