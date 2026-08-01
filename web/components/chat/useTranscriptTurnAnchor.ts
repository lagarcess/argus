"use client";

import {
  useCallback,
  useLayoutEffect,
  type Dispatch,
  type MutableRefObject,
  type RefObject,
  type SetStateAction,
} from "react";
import type { Message } from "@/components/chat/types";

export type PendingMessageAnchor = {
  conversationId: string;
  messageId: string;
} | null;

export type PendingScrollRestore = {
  conversationId: string;
  scrollTop: number | null;
} | null;

type TranscriptTurnAnchorParams = {
  conversationId: string | null;
  messages: Message[];
  jumpToLatestThresholdPx: number;
  activeConversationIdRef: MutableRefObject<string | null>;
  pendingMessageAnchorRef: MutableRefObject<PendingMessageAnchor>;
  pendingScrollRestoreRef: MutableRefObject<PendingScrollRestore>;
  messageElementRefs: MutableRefObject<Map<string, HTMLDivElement>>;
  scrollContainerRef: RefObject<HTMLDivElement | null>;
  shouldAutoScrollRef: MutableRefObject<boolean>;
  setShowJumpToLatest: Dispatch<SetStateAction<boolean>>;
};

/**
 * Owns anchoring the transcript to a specific turn: pending-load message
 * anchors, session scroll restore, and rail jumps all mark the transcript
 * detached from the live tail so auto-scroll cannot fight the reader.
 */
export function useTranscriptTurnAnchor({
  conversationId,
  messages,
  jumpToLatestThresholdPx,
  activeConversationIdRef,
  pendingMessageAnchorRef,
  pendingScrollRestoreRef,
  messageElementRefs,
  scrollContainerRef,
  shouldAutoScrollRef,
  setShowJumpToLatest,
}: TranscriptTurnAnchorParams): {
  anchorToTurn: (messageId: string) => void;
} {
  useLayoutEffect(() => {
    const pendingAnchor = pendingMessageAnchorRef.current;
    if (
      pendingAnchor &&
      pendingAnchor.conversationId === conversationId &&
      pendingAnchor.conversationId === activeConversationIdRef.current
    ) {
      const element = messageElementRefs.current.get(pendingAnchor.messageId);
      if (element) {
        element.scrollIntoView({ block: "center" });
        element.focus({ preventScroll: true });
        pendingMessageAnchorRef.current = null;
        pendingScrollRestoreRef.current = null;
        shouldAutoScrollRef.current = false;
        setShowJumpToLatest(true);
        return;
      }
    }
    const pending = pendingScrollRestoreRef.current;
    const container = scrollContainerRef.current;
    if (
      !pending ||
      !container ||
      pending.conversationId !== conversationId ||
      pending.conversationId !== activeConversationIdRef.current
    ) {
      return;
    }
    container.scrollTop = pending.scrollTop ?? container.scrollHeight;
    pendingScrollRestoreRef.current = null;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceFromBottom <= jumpToLatestThresholdPx;
    shouldAutoScrollRef.current =
      pending.scrollTop === null ? true : isNearBottom;
    setShowJumpToLatest(distanceFromBottom > jumpToLatestThresholdPx);
  }, [
    conversationId,
    messages,
    jumpToLatestThresholdPx,
    activeConversationIdRef,
    pendingMessageAnchorRef,
    pendingScrollRestoreRef,
    messageElementRefs,
    scrollContainerRef,
    shouldAutoScrollRef,
    setShowJumpToLatest,
  ]);

  const anchorToTurn = useCallback(
    (messageId: string) => {
      const element = messageElementRefs.current.get(messageId);
      if (!element) return;
      element.scrollIntoView({ block: "center", behavior: "smooth" });
      element.focus({ preventScroll: true });
      shouldAutoScrollRef.current = false;
      setShowJumpToLatest(true);
    },
    [messageElementRefs, shouldAutoScrollRef, setShowJumpToLatest],
  );

  return { anchorToTurn };
}
