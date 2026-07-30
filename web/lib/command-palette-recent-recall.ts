import type {
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
  conversationIds: readonly string[];
  fetchRecall: (params: RecentRecallRequest) => Promise<SearchResponse>;
  isCurrent?: () => boolean;
};

export async function loadCommandPaletteRecentRecall({
  conversationIds,
  fetchRecall,
  isCurrent = () => true,
}: LoadRecentRecallParams): Promise<SearchResponse | null> {
  const visibleIds = [...new Set(conversationIds.filter(Boolean))];
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
  if (recalledById.size !== targetIds.size) {
    throw new Error("Recent recall is missing visible conversations.");
  }

  return {
    items: visibleIds.map((id) => recalledById.get(id)!),
    next_cursor: null,
    ledger_groups: response.ledger_groups ?? [],
  };
}
