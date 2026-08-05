"use client";

import { useCallback } from "react";

const JUMP_TO_LATEST_THRESHOLD_PX = 240;

export const chatScrollPositionState = (distanceFromBottom: number) => ({
  shouldAutoScroll: distanceFromBottom <= JUMP_TO_LATEST_THRESHOLD_PX,
  showJumpToLatest: distanceFromBottom > JUMP_TO_LATEST_THRESHOLD_PX,
});

export const executeChatTranscriptUpdateScroll = (options: Readonly<{
  shouldAutoScrollRef: { current: boolean };
  scrollToLatest: (behavior?: ScrollBehavior) => void;
  updateScrollPositionState: () => void;
}>): void => {
  if (options.shouldAutoScrollRef.current) {
    options.scrollToLatest("smooth");
    return;
  }
  options.updateScrollPositionState();
};

type UseChatScrollControlsOptions = {
  accountUserId: string | undefined;
  activeConversationIdRef: { current: string | null };
  readyTranscriptConversationIdRef: { current: string | null };
  bottomRef: { current: HTMLDivElement | null };
  scrollContainerRef: { current: HTMLDivElement | null };
  shouldAutoScrollRef: { current: boolean };
  transcriptSessionCache: {
    rememberScroll: (input: {
      userId: string;
      conversationId: string;
      scrollTop: number;
    }) => void;
  };
  setShowJumpToLatest: (show: boolean) => void;
};

export function useChatScrollControls({
  accountUserId,
  activeConversationIdRef,
  readyTranscriptConversationIdRef,
  bottomRef,
  scrollContainerRef,
  shouldAutoScrollRef,
  transcriptSessionCache,
  setShowJumpToLatest,
}: UseChatScrollControlsOptions) {
  const updateScrollPositionState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const activeTranscriptId = readyTranscriptConversationIdRef.current;
    if (
      activeTranscriptId &&
      accountUserId &&
      activeTranscriptId === activeConversationIdRef.current
    ) {
      transcriptSessionCache.rememberScroll({
        userId: accountUserId,
        conversationId: activeTranscriptId,
        scrollTop: container.scrollTop,
      });
    }
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const nextState = chatScrollPositionState(distanceFromBottom);
    shouldAutoScrollRef.current = nextState.shouldAutoScroll;
    setShowJumpToLatest(nextState.showJumpToLatest);
  }, [
    accountUserId,
    activeConversationIdRef,
    readyTranscriptConversationIdRef,
    scrollContainerRef,
    setShowJumpToLatest,
    shouldAutoScrollRef,
    transcriptSessionCache,
  ]);

  const scrollToLatest = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      bottomRef.current?.scrollIntoView({ behavior });
      shouldAutoScrollRef.current = true;
      setShowJumpToLatest(false);
    },
    [bottomRef, setShowJumpToLatest, shouldAutoScrollRef],
  );

  return { scrollToLatest, updateScrollPositionState };
}
