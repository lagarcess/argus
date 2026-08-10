import type { TFunction } from "i18next";
import {
  addConfirmationPeerAssets,
  directEditConfirmation,
  restoreConfirmationAssets,
  type ApiMessage,
} from "@/lib/argus-api";
import type {
  ChatActionOption,
  ConfirmationDirectEditPayload,
  Message,
} from "./types";

/**
 * Non-turn confirmation mutations: peer add, peer undo, direct edits. The
 * dividing line of the edit contract is whether a turn was spent, not which
 * affordance was used: these spend nothing, so the backend rewrites the same
 * card message and this module replaces it in place. Nothing here can append
 * to the transcript; the frontend never invents card state. Factory over a
 * dependency getter, matching omnisearchActionHandlers, so ChatInterface
 * stays orchestration.
 */

type SupersedingDeps = {
  activeConversationId: () => string | null;
  activeConfirmationId: () => string | null;
  hydrate: (created: ApiMessage[]) => { messages: Message[] };
  setMessages: (updater: (prev: Message[]) => Message[]) => void;
  showToast: (
    message: string,
    variant?: "neutral" | "error",
    options?: {
      action?: { label: string; onPress: () => void };
      durationMs?: number;
    },
  ) => void;
  hideToast: () => void;
  t: TFunction;
};

export function confirmationSupersedingHandlers(deps: () => SupersedingDeps) {
  function replaceCardMessageInPlace(updated: ApiMessage): boolean {
    const { hydrate, setMessages } = deps();
    const hydrated = hydrate([updated]).messages;
    if (hydrated.length === 0) {
      return false;
    }
    const replacement = hydrated[0];
    setMessages((prev) =>
      prev.map((message) =>
        message.id === replacement.id ? replacement : message,
      ),
    );
    return true;
  }

  async function handleDirectEditConfirmation(
    confirmationId: string,
    edit: ConfirmationDirectEditPayload,
  ): Promise<void> {
    const { activeConversationId } = deps();
    const targetConversationId = activeConversationId();
    if (!targetConversationId) {
      throw new Error("no_active_conversation");
    }
    // Errors propagate so the editor can show them inline next to the inputs.
    const updated = await directEditConfirmation(
      targetConversationId,
      confirmationId,
      edit,
    );
    if (!replaceCardMessageInPlace(updated)) {
      throw new Error("edited_confirmation_missing");
    }
  }

  async function handleUndoConfirmationPeer(): Promise<void> {
    const { activeConversationId, activeConfirmationId, hideToast, showToast, t } =
      deps();
    const targetConversationId = activeConversationId();
    const activeId = activeConfirmationId();
    if (!targetConversationId || !activeId) return;
    hideToast();
    try {
      const restored = await restoreConfirmationAssets(
        targetConversationId,
        activeId,
      );
      replaceCardMessageInPlace(restored);
    } catch {
      showToast(
        t(
          "chat.confirmation.peer_add_failed",
          "Couldn't change that test. The card is unchanged.",
        ),
        "error",
      );
    }
  }

  async function handleAddConfirmationPeer(
    action: ChatActionOption,
  ): Promise<void> {
    const { activeConversationId, activeConfirmationId, showToast, t } = deps();
    const payload = action.payload ?? {};
    const symbols = Array.isArray(payload.symbols)
      ? payload.symbols.map((symbol) => String(symbol)).filter(Boolean)
      : [];
    const targetConversationId = activeConversationId();
    const confirmationId =
      String(payload.confirmation_id ?? "") || activeConfirmationId();
    if (!targetConversationId || !confirmationId || symbols.length === 0) {
      return;
    }
    try {
      const updated = await addConfirmationPeerAssets(
        targetConversationId,
        confirmationId,
        symbols,
      );
      if (!replaceCardMessageInPlace(updated)) {
        return;
      }
      // Motion is the feedback; the toast carries Undo, not information.
      // Quick successive adds replace the single toast, and each Undo steps
      // back exactly one add.
      showToast("", "neutral", {
        action: {
          label: t("chat.confirmation.undo", "Undo"),
          onPress: () => void handleUndoConfirmationPeer(),
        },
        durationMs: 6000,
      });
    } catch {
      showToast(
        t(
          "chat.confirmation.peer_add_failed",
          "Couldn't add that asset to this test. The rest of the card is unchanged.",
        ),
        "error",
      );
    }
  }

  return {
    handleAddConfirmationPeer,
    handleDirectEditConfirmation,
    handleUndoConfirmationPeer,
  };
}
