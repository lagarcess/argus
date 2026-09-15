import { CHAT_RUNTIME_EVENT_TIMEOUT_MS } from "./chat-runtime-timeout";
import type { ApiMessage } from "./argus-api";
import { loadAllConversationMessagePages } from "./chat-message-hydration";
import { hydrateMessagesFromApi } from "@/components/chat/chat-message-projection";
import type { Message } from "@/components/chat/types";

export type SavedConversationTranscript = {
  messages: Message[];
  latestMessageId: string | null;
  unansweredUserMessage: { id: string; createdAt: string } | null;
};

export async function loadSavedConversationTranscript(
  conversationId: string,
  signal?: AbortSignal,
): Promise<SavedConversationTranscript> {
  const items: ApiMessage[] = await loadAllConversationMessagePages(conversationId, undefined, { signal });
  const last = items.at(-1);
  return {
    messages: hydrateMessagesFromApi(items).messages,
    latestMessageId: last?.id ?? null,
    unansweredUserMessage: last?.role === "user" ? { id: last.id, createdAt: last.created_at } : null,
  };
}

export type TranscriptFreshnessInputs = {
  accountId: string | null;
  conversationId: string | null;
  latestMessageId: string | null;
  activityRevision: number;
  requestId: string | null;
  ready: boolean;
  visibleMessages: readonly Pick<Message, "id" | "role">[];
};

const identity = (inputs: Pick<TranscriptFreshnessInputs, "accountId" | "conversationId">) =>
  inputs.accountId && inputs.conversationId ? JSON.stringify([inputs.accountId, inputs.conversationId]) : null;

const REPLY_CHECK_INTERVAL_MS = 2_000;
export type TranscriptReplyClock = {
  now: () => number;
  schedule: (callback: () => void, delayMs: number) => () => void;
};
const browserReplyClock: TranscriptReplyClock = {
  now: () => Date.now(),
  schedule: (callback, delayMs) => {
    const timer = setTimeout(callback, delayMs);
    return () => clearTimeout(timer);
  },
};

/** Compares API identity with the snapshot actually loaded, independently of work/unread state. */
export function createTranscriptFreshnessRuntime(options: {
  load: (conversationId: string, signal: AbortSignal) => Promise<SavedConversationTranscript>;
  apply: (conversationId: string, snapshot: SavedConversationTranscript) => void;
  clock?: TranscriptReplyClock;
}) {
  const clock = options.clock ?? browserReplyClock;
  let apply = options.apply;
  let inputs: TranscriptFreshnessInputs | null = null;
  let loaded: {
    identity: string;
    latestMessageId: string | null;
    unansweredUserId: string | null;
    replyDeadline: number | null;
  } | null = null;
  let pending: { identity: string; controller: AbortController; replyCheck: boolean } | null = null;
  let attempted: string | null = null;
  const cancel = () => { pending?.controller.abort(); pending = null; };
  let replyTimer: { key: string; cancel: () => void } | null = null;
  const stopReplyTimer = () => { replyTimer?.cancel(); replyTimer = null; };
  const awaitingReply = () => {
    if (!inputs || !inputs.ready || inputs.requestId || !loaded ||
      loaded.identity !== identity(inputs) || loaded.replyDeadline === null ||
      clock.now() >= loaded.replyDeadline) return null;
    const userIndex = inputs.visibleMessages.findIndex((message) => message.id === loaded!.unansweredUserId);
    const replyIndex = inputs.visibleMessages.findIndex((message) =>
      message.role === "ai" && message.id === inputs!.latestMessageId);
    if (userIndex >= 0 && replyIndex > userIndex) return null;
    return { key: JSON.stringify([loaded.identity, loaded.unansweredUserId]), deadline: loaded.replyDeadline };
  };
  const synchronizeReplyTimer = () => {
    const waiting = awaitingReply();
    if (replyTimer?.key === waiting?.key) return;
    stopReplyTimer();
    if (!waiting) return;
    replyTimer = {
      key: waiting.key,
      cancel: clock.schedule(() => {
        replyTimer = null;
        if (!awaitingReply()) {
          if (pending?.replyCheck) cancel();
          return;
        }
        if (inputs) update(inputs, true);
        synchronizeReplyTimer();
      }, Math.min(REPLY_CHECK_INTERVAL_MS, waiting.deadline - clock.now())),
    };
  };
  const recordLoaded = (accountId: string, conversationId: string, snapshot: SavedConversationTranscript) => {
    const key = JSON.stringify([accountId, conversationId]);
    const user = snapshot.unansweredUserMessage;
    const savedAt = user ? Date.parse(user.createdAt) : NaN;
    const sameUser = loaded?.identity === key && loaded.unansweredUserId === user?.id;
    loaded = {
      identity: key,
      latestMessageId: snapshot.latestMessageId,
      unansweredUserId: user?.id ?? null,
      // Re-reading the same unanswered message never extends its turn window.
      replyDeadline: sameUser ? loaded!.replyDeadline : Number.isFinite(savedAt)
        ? Math.min(savedAt, clock.now()) + CHAT_RUNTIME_EVENT_TIMEOUT_MS : null,
    };
    synchronizeReplyTimer();
  };
  const update = (next: TranscriptFreshnessInputs, replyCheck = false) => {
    const previousIdentity = inputs ? identity(inputs) : null;
    inputs = next;
    const key = identity(next);
    if (key !== previousIdentity || next.requestId || !next.ready) {
      cancel();
      attempted = null;
    }
    synchronizeReplyTimer();
    if (!key || !next.ready || next.requestId || !next.conversationId) return;
    if (!replyCheck && (!next.latestMessageId ||
      (loaded?.identity === key && loaded.latestMessageId === next.latestMessageId))) return;
    // Final SSE payload ids are server-owned too. The sending tab already has
    // this reply and must not replace its stream with a redundant read.
    if (!replyCheck && next.latestMessageId && next.visibleMessages.some((message) => message.id === next.latestMessageId)) return;
    if (pending) return;
    const attempt = JSON.stringify([key, next.latestMessageId, next.activityRevision]);
    if (!replyCheck && attempted === attempt) return;
    attempted = attempt;
    const controller = new AbortController();
    const request = { identity: key, controller, replyCheck };
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
  return { update, recordLoaded, retry, setApply: (next: typeof apply) => { apply = next; }, dispose: () => { stopReplyTimer(); cancel(); } };
}
