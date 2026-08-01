import { retestActionOption } from "@/lib/chat-retest";
import type { ChatActionOption } from "./types";

type OmnisearchActionDeps = {
  closeOverlay: () => void;
  loadConversation: (
    conversationId: string,
    messageId?: string,
    openAtLeftOff?: boolean,
  ) => Promise<unknown> | unknown;
  send: (
    text: string,
    action?: ChatActionOption,
  ) => Promise<boolean> | boolean;
  isSourceConversationReady: (conversationId: string) => boolean;
};

export type OmnisearchActions = {
  retest: (conversationId: string, sourceRunId: string) => Promise<void>;
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
  };
}
