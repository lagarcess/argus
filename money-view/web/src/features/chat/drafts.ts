const PREFIX = 'argus-chat-draft:v1';

type StagedDraft = {
  text: string;
  status: 'ready' | 'submitted';
  turn_id: string | null;
  created_at: string;
};

function key(workspaceKey: string, draftId: string) {
  return `${PREFIX}:${workspaceKey}:${draftId}`;
}

function parse(value: string | null): StagedDraft | null {
  if (!value) return null;
  try {
    const draft = JSON.parse(value) as Partial<StagedDraft>;
    return typeof draft.text === 'string' && (draft.status === 'ready' || draft.status === 'submitted') && typeof draft.created_at === 'string' && (draft.turn_id === null || typeof draft.turn_id === 'string')
      ? draft as StagedDraft
      : null;
  } catch { return null; }
}

/** Stages user-authored text inside its current workspace and returns an opaque route id. */
export function stageChatDraft(workspaceKey: string, text: string) {
  const draftId = crypto.randomUUID();
  sessionStorage.setItem(key(workspaceKey, draftId), JSON.stringify({ text, status: 'ready', turn_id: null, created_at: new Date().toISOString() } satisfies StagedDraft));
  return draftId;
}

export function readChatDraft(workspaceKey: string, draftId: string) {
  return parse(sessionStorage.getItem(key(workspaceKey, draftId)));
}

export function markChatDraftSubmitted(workspaceKey: string, draftId: string) {
  const draft = readChatDraft(workspaceKey, draftId);
  if (!draft || draft.status !== 'ready') return null;
  const submitted = { ...draft, status: 'submitted' as const, turn_id: draft.turn_id ?? crypto.randomUUID() };
  sessionStorage.setItem(key(workspaceKey, draftId), JSON.stringify(submitted));
  return submitted;
}

/** Reuses a submitted handoff's original turn only when its user text is unchanged. */
export function stagedChatTurnId(workspaceKey: string, draftId: string, text: string) {
  const draft = readChatDraft(workspaceKey, draftId);
  return draft?.status === 'submitted' && draft.text === text ? draft.turn_id : null;
}

/** Keeps pre-delivery edits with the staged handoff without reusing a sent turn for changed text. */
export function updateChatDraftText(workspaceKey: string, draftId: string, text: string) {
  const draft = readChatDraft(workspaceKey, draftId);
  if (!draft || draft.text === text) return draft;
  const updated = { ...draft, text, turn_id: draft.status === 'submitted' ? null : draft.turn_id };
  sessionStorage.setItem(key(workspaceKey, draftId), JSON.stringify(updated));
  return updated;
}

export function clearChatDraft(workspaceKey: string, draftId: string) {
  sessionStorage.removeItem(key(workspaceKey, draftId));
}

export function conversationDraftKey(workspaceKey: string, conversationId: string) {
  return key(workspaceKey, `conversation:${conversationId}`);
}
