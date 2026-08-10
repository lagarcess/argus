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
 * No-turn confirmation mutations: peer add, peer undo, direct capital/date
 * edit. Each calls its typed endpoint and appends the superseding card the
 * backend returns; the frontend never invents card state. Factory over a
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
  function appendSupersedingConfirmation(created: ApiMessage): boolean {
    const { hydrate, setMessages } = deps();
    const hydrated = hydrate([created]).messages;
    if (hydrated.length === 0) {
      return false;
    }
    setMessages((prev) => [
      // The new card supersedes the old one; mirror the reload projection
      // instead of leaving two active cards on screen.
      ...prev.map((message) =>
        message.confirmation &&
        message.confirmation.confirmation_state !== "cancelled" &&
        message.confirmation.confirmation_id !==
          hydrated[0].confirmation?.confirmation_id
          ? {
              ...message,
              confirmation: {
                ...message.confirmation,
                confirmation_state: "superseded" as const,
              },
            }
          : message,
      ),
      ...hydrated,
    ]);
    return true;
  }

  async function handleDirectEditConfirmation(
    confirmationId: string,
    edit: ConfirmationDirectEditPayload,
  ): Promise<void> {
    const { activeConversationId, hydrate, setMessages } = deps();
    const targetConversationId = activeConversationId();
    if (!targetConversationId) {
      throw new Error("no_active_conversation");
    }
    // No turn is spent and nothing new appears: the typed endpoint updates
    // the same card in place and returns the same message, edited. Errors
    // propagate so the editor can show them inline next to the inputs.
    const updated = await directEditConfirmation(
      targetConversationId,
      confirmationId,
      edit,
    );
    const hydrated = hydrate([updated]).messages;
    if (hydrated.length === 0) {
      throw new Error("edited_confirmation_missing");
    }
    const replacement = hydrated[0];
    setMessages((prev) =>
      prev.map((message) =>
        message.id === replacement.id ? replacement : message,
      ),
    );
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
      appendSupersedingConfirmation(restored);
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
      const created = await addConfirmationPeerAssets(
        targetConversationId,
        confirmationId,
        symbols,
      );
      if (!appendSupersedingConfirmation(created)) {
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
