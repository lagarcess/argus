import { retestActionOption } from "@/lib/chat-retest";
import { decideGuestNewConversationGate } from "@/lib/guest-capability-gates";
import type { SendOptions } from "./chat-send-selection";
import type { ChatActionOption } from "./types";

type OmnisearchActionDeps = {
  closeOverlay: () => void;
  loadConversation: (
    conversationId: string,
    messageId?: string,
    openAtLeftOff?: boolean,
  ) => Promise<unknown> | unknown;
  startNewChat: () => Promise<unknown> | unknown;
  /** The existing new-chat request, which offers a guest the non-empty choice. */
  requestNewChat: () => void;
  guestGate: () => Parameters<typeof decideGuestNewConversationGate>[0];
  send: (
    text: string,
    action?: ChatActionOption,
    actionArg?: ChatActionOption,
    options?: SendOptions,
  ) => Promise<boolean> | boolean;
  isSourceConversationReady: (conversationId: string) => boolean;
};

export type OmnisearchActions = {
  retest: (conversationId: string, sourceRunId: string) => Promise<void>;
  ask: (text: string) => Promise<void>;
};

/**
 * Omnisearch actions submit into the source conversation, so each one waits for
 * the shipped conversation-isolation contract before sending. Dependencies are
 * read at event time, never during render.
 */
export function omnisearchActionHandlers(
  readDeps: () => OmnisearchActionDeps,
): OmnisearchActions {
  const submitToSourceConversation = async (
    conversationId: string,
    submit: (deps: OmnisearchActionDeps) => void,
  ) => {
    const deps = readDeps();
    deps.closeOverlay();
    await deps.loadConversation(conversationId, undefined, true);
    if (!deps.isSourceConversationReady(conversationId)) return;
    submit(deps);
  };

  return {
    retest: (conversationId, sourceRunId) =>
      submitToSourceConversation(conversationId, (deps) => {
        const action = retestActionOption(sourceRunId);
        void deps.send(action.label, action);
      }),
    // Ask Argus: the typed text starts a new chat through the ordinary send
    // path, and nothing runs until the user presses Enter on the row. A guest
    // whose chat already has content keeps today's rule: the existing choice.
    ask: async (text) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const deps = readDeps();
      deps.closeOverlay();
      if (decideGuestNewConversationGate(deps.guestGate()).kind === "choose_non_empty") {
        deps.requestNewChat();
        return;
      }
      await deps.startNewChat();
      void deps.send(trimmed, undefined, undefined, { startNewConversation: true });
    },
  };
}
