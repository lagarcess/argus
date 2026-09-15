import type { ApiMessage } from "./argus-api";
import { loadAllConversationMessagePages } from "./chat-message-hydration";
import { hydrateMessagesFromApi } from "@/components/chat/chat-message-projection";
import type { Message } from "@/components/chat/types";

export type SavedConversationTranscript = {
  messages: Message[];
  latestMessageId: string | null;
};

export async function loadSavedConversationTranscript(
  conversationId: string,
  signal?: AbortSignal,
): Promise<SavedConversationTranscript> {
  const items: ApiMessage[] = await loadAllConversationMessagePages(conversationId, undefined, { signal });
  return { messages: hydrateMessagesFromApi(items).messages, latestMessageId: items.at(-1)?.id ?? null };
}

export type TranscriptFreshnessInputs = {
  accountId: string | null;
  conversationId: string | null;
  latestMessageId: string | null;
  activityRevision: number;
  requestId: string | null;
  ready: boolean;
  visibleMessageIds: ReadonlySet<string>;
};

const identity = (inputs: Pick<TranscriptFreshnessInputs, "accountId" | "conversationId">) =>
  inputs.accountId && inputs.conversationId ? JSON.stringify([inputs.accountId, inputs.conversationId]) : null;

/** Compares API identity with the snapshot actually loaded, independently of work/unread state. */
export function createTranscriptFreshnessRuntime(options: {
  load: (conversationId: string, signal: AbortSignal) => Promise<SavedConversationTranscript>;
  apply: (conversationId: string, snapshot: SavedConversationTranscript) => void;
}) {
  let apply = options.apply;
  let inputs: TranscriptFreshnessInputs | null = null;
  let loaded: { identity: string; latestMessageId: string | null } | null = null;
  let pending: { identity: string; controller: AbortController } | null = null;
  let attempted: string | null = null;
  const cancel = () => { pending?.controller.abort(); pending = null; };
  const recordLoaded = (accountId: string, conversationId: string, snapshot: SavedConversationTranscript) => {
    loaded = { identity: JSON.stringify([accountId, conversationId]), latestMessageId: snapshot.latestMessageId };
  };
  const update = (next: TranscriptFreshnessInputs) => {
    const previousIdentity = inputs ? identity(inputs) : null;
    inputs = next;
    const key = identity(next);
    if (key !== previousIdentity || next.requestId || !next.ready) {
      cancel();
      attempted = null;
    }
    if (!key || !next.ready || next.requestId || !next.latestMessageId || !next.conversationId) return;
    if (loaded?.identity === key && loaded.latestMessageId === next.latestMessageId) return;
    // Final SSE payload ids are server-owned too. The sending tab already has
    // this reply and must not replace its stream with a redundant read.
    if (next.visibleMessageIds.has(next.latestMessageId)) return;
    if (pending) return;
    const attempt = JSON.stringify([key, next.latestMessageId, next.activityRevision]);
    if (attempted === attempt) return;
    attempted = attempt;
    const controller = new AbortController();
    const request = { identity: key, controller };
    pending = request;
    const conversationId = next.conversationId;
    void options.load(conversationId, controller.signal).then((snapshot) => {
      if (pending !== request || !inputs || identity(inputs) !== key || inputs.requestId || !inputs.ready) return;
      recordLoaded(inputs.accountId!, conversationId, snapshot);
      apply(conversationId, snapshot);
    }).catch(() => {
      // Keep the readable transcript. The next activity/focus update retries.
    }).finally(() => {
      if (pending === request) {
        pending = null;
        if (inputs) update(inputs);
      }
    });
  };
  const retry = () => { attempted = null; if (inputs) update(inputs); };
  return { update, recordLoaded, retry, setApply: (next: typeof apply) => { apply = next; }, dispose: cancel };
}
