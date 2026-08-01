"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  listConversations,
  type HistoryItem,
} from "@/lib/argus-api";
import {
  mergeRecentChats,
  projectConversationToRecentChat,
  refreshFirstPageRecentChats,
} from "@/lib/chat-recents";

type UseRecentConversationsOptions = Readonly<{
  guestExpiresAt?: string | null;
}>;

type RecentConversationsState = {
  historyItems: HistoryItem[];
  setHistoryItems: Dispatch<SetStateAction<HistoryItem[]>>;
  historyNextCursor: string | null;
  isLoadingMoreHistory: boolean;
  hasRequestedOlderHistory: boolean;
  historyLoadMoreError: boolean;
  loadHistoryPage: (
    nextCursor?: string | null,
    append?: boolean,
  ) => Promise<void>;
  clearHistory: () => void;
  loadMoreHistory: () => void;
  refreshHistory: () => void;
};

export function useRecentConversations({
  guestExpiresAt,
}: UseRecentConversationsOptions): RecentConversationsState {
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyNextCursor, setHistoryNextCursor] = useState<string | null>(
    null,
  );
  const [isLoadingMoreHistory, setIsLoadingMoreHistory] = useState(false);
  const [hasRequestedOlderHistory, setHasRequestedOlderHistory] =
    useState(false);
  const [historyLoadMoreError, setHistoryLoadMoreError] = useState(false);
  const paginationInFlightRef = useRef(false);
  const pageRequestsRef = useRef(new Map<string, Promise<void>>());
  const firstPageConversationIdsRef = useRef<Set<string>>(new Set());
  const guestExpiresAtRef = useRef(guestExpiresAt);

  useEffect(() => {
    guestExpiresAtRef.current = guestExpiresAt;
  }, [guestExpiresAt]);

  const loadHistoryPage = useCallback(
    (nextCursor?: string | null, append = false) => {
      const requestKey = nextCursor ?? "first-page";
      const existingRequest = pageRequestsRef.current.get(requestKey);
      if (existingRequest) return existingRequest;

      const request = listConversations({
        limit: 30,
        cursor: nextCursor ?? undefined,
        archived: false,
        deleted: false,
      })
        .then(({ items, next_cursor }) => {
          const projected = items
            .filter(
              (conversation) => conversation.last_message_preview !== null,
            )
            .map((conversation) =>
              projectConversationToRecentChat(conversation, {
                guestExpiresAt: guestExpiresAtRef.current,
              }),
            );
          if (append) {
            setHistoryItems((current) => mergeRecentChats(current, projected));
          } else {
            setHistoryItems((current) =>
              refreshFirstPageRecentChats(
                current,
                firstPageConversationIdsRef.current,
                projected,
              ),
            );
            firstPageConversationIdsRef.current = new Set(
              projected.map((item) => item.conversation_id ?? item.id),
            );
          }
          setHistoryNextCursor(next_cursor);
        })
        .finally(() => {
          pageRequestsRef.current.delete(requestKey);
        });
      pageRequestsRef.current.set(requestKey, request);
      return request;
    },
    [],
  );

  const refreshHistory = useCallback(() => {
    const runRefresh = () => loadHistoryPage(null, false);
    const inFlightFirstPage =
      pageRequestsRef.current.get("first-page");
    const refreshRequest = inFlightFirstPage
      ? inFlightFirstPage.then(runRefresh, runRefresh)
      : runRefresh();
    void refreshRequest.catch(() => undefined);
  }, [loadHistoryPage]);

  const clearHistory = useCallback(() => {
    setHistoryItems([]);
    setHistoryNextCursor(null);
    setHasRequestedOlderHistory(false);
    setHistoryLoadMoreError(false);
    pageRequestsRef.current.clear();
    firstPageConversationIdsRef.current.clear();
    paginationInFlightRef.current = false;
  }, []);

  const loadMoreHistory = useCallback(() => {
    if (!historyNextCursor || paginationInFlightRef.current) return;
    paginationInFlightRef.current = true;
    setHasRequestedOlderHistory(true);
    setHistoryLoadMoreError(false);
    setIsLoadingMoreHistory(true);
    void loadHistoryPage(historyNextCursor, true)
      .catch(() => setHistoryLoadMoreError(true))
      .finally(() => {
        paginationInFlightRef.current = false;
        setIsLoadingMoreHistory(false);
      });
  }, [historyNextCursor, loadHistoryPage]);

  useEffect(() => {
    void loadHistoryPage(null, false).catch(() => undefined);
  }, [loadHistoryPage]);

  return {
    historyItems,
    setHistoryItems,
    historyNextCursor,
    isLoadingMoreHistory,
    hasRequestedOlderHistory,
    historyLoadMoreError,
    loadHistoryPage,
    clearHistory,
    loadMoreHistory,
    refreshHistory,
  };
}
