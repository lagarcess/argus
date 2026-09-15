"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import type { Message } from "./types";
import type { ConversationActivityTranscriptReadiness } from "./useConversationActivityViewport";
import {
  createTranscriptFreshnessRuntime,
  loadSavedConversationTranscript,
  type TranscriptFreshnessInputs,
  type SavedConversationTranscript,
} from "@/lib/conversation-transcript-freshness";

export function useConversationTranscriptFreshness(options: {
  inputs: () => TranscriptFreshnessInputs;
  invalidate: (id: string) => void;
  readyTranscriptConversationIdRef: { current: string | null };
  activityTranscriptReadiness: ConversationActivityTranscriptReadiness;
  pendingScrollRestoreRef: { current: { conversationId: string; scrollTop: number | null } | null };
  scrollContainerRef: { current: HTMLDivElement | null };
  shouldAutoScrollRef: { current: boolean };
  setMessages: (messages: Message[]) => void;
}) {
  const { readyTranscriptConversationIdRef, pendingScrollRestoreRef, scrollContainerRef, shouldAutoScrollRef } = options;
  const apply = (id: string, snapshot: SavedConversationTranscript) => {
    options.invalidate(id);
    readyTranscriptConversationIdRef.current = id;
    options.activityTranscriptReadiness.stageCanonical(id);
    pendingScrollRestoreRef.current = { conversationId: id, scrollTop: scrollContainerRef.current?.scrollTop ?? 0 };
    shouldAutoScrollRef.current = false;
    options.setMessages(snapshot.messages);
  };
  const [runtime] = useState(() => createTranscriptFreshnessRuntime({ load: loadSavedConversationTranscript, apply: () => undefined }));
  useLayoutEffect(() => { runtime.setApply(apply); runtime.update(options.inputs()); });
  useEffect(() => {
    const resume = () => { if (document.visibilityState === "visible") runtime.retry(); };
    window.addEventListener("focus", resume);
    document.addEventListener("visibilitychange", resume);
    return () => {
      window.removeEventListener("focus", resume);
      document.removeEventListener("visibilitychange", resume);
      runtime.dispose();
    };
  }, [runtime]);
  return runtime.recordLoaded;
}
