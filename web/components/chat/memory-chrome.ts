"use client";

// Chat-facing memory chrome: availability, per-conversation private-chat
// state, and the final-payload recall reader. Kept out of ChatInterface so
// the memory concern stays one cohesive module.

import { useCallback, useEffect, useState } from "react";
import { memoryRecallsFromValue, type MemoryRecallItem } from "@/lib/memory-recalls";
import {
  isConversationMemoryOptOut,
  memoryAvailable,
  setConversationMemoryOptOut,
} from "@/lib/memory-privacy";

export type MemoryChrome = {
  controlsAvailable: boolean;
  optOut: boolean;
  proposalEnabled: boolean;
  onToggleOptOut: () => void;
};

export function useMemoryChrome(
  isGuest: boolean,
  conversationId: string | null,
): MemoryChrome {
  const [controlsAvailable, setControlsAvailable] = useState(false);
  const [optOut, setOptOut] = useState(false);

  // Memory chrome stays invisible unless the backend exposes it.
  useEffect(() => {
    if (isGuest) return;
    let isCurrent = true;
    void memoryAvailable().then((available) => {
      if (isCurrent) setControlsAvailable(available);
    });
    return () => {
      isCurrent = false;
    };
  }, [isGuest]);

  useEffect(() => {
    setOptOut(conversationId ? isConversationMemoryOptOut(conversationId) : false);
  }, [conversationId]);

  const onToggleOptOut = useCallback(() => {
    if (!conversationId) return;
    setOptOut((current) => {
      const next = !current;
      setConversationMemoryOptOut(conversationId, next);
      return next;
    });
  }, [conversationId]);

  return {
    controlsAvailable,
    optOut,
    proposalEnabled: controlsAvailable && !optOut,
    onToggleOptOut,
  };
}

export function memoryRecallsFromFinalPayload(
  finalPayload: unknown,
): MemoryRecallItem[] | null {
  if (typeof finalPayload !== "object" || finalPayload === null) return null;
  return memoryRecallsFromValue(
    (finalPayload as Record<string, unknown>).memory_recalls,
  );
}
