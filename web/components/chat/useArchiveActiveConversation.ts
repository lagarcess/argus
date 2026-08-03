"use client";

import { useCallback, useRef } from "react";
import { patchConversation } from "@/lib/argus-api";

type UseArchiveActiveConversationInput = {
  conversationId: string | null;
  onArchived: (conversationId: string) => void;
  onError: () => void;
  onSuccess: () => void;
};

export function useArchiveActiveConversation({
  conversationId,
  onArchived,
  onError,
  onSuccess,
}: UseArchiveActiveConversationInput) {
  const inFlightRef = useRef(false);

  return useCallback(async () => {
    if (!conversationId || inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      await patchConversation(conversationId, { archived: true });
      onSuccess();
      onArchived(conversationId);
    } catch {
      onError();
    } finally {
      inFlightRef.current = false;
    }
  }, [conversationId, onArchived, onError, onSuccess]);
}
