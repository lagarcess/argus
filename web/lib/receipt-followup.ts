import { loadAllConversationMessagePages, resolveOrdinaryTransportAmbiguity } from './chat-message-hydration';
import { apiFetch } from './argus-api-transport';
import type { ReceiptFollowupIntent } from './receipt-followup-storage';
export { createReceiptFollowup, saveReceiptFollowup, readReceiptFollowup, clearReceiptFollowup, type ReceiptFollowupIntent } from './receipt-followup-storage';

type ReceiptFollowupPhase = 'initial' | 'working' | 'choice' | 'conversion' | 'hydrating' | 'error' | 'unavailable' | 'done';

/** One synchronous owner for effect admission and React's phase projection. */
export function createReceiptFollowupLifecycle() {
  let phase: ReceiptFollowupPhase = 'initial';
  const listeners = new Set<() => void>();
  const set = (next: ReceiptFollowupPhase) => {
    if (phase === next) return;
    phase = next;
    listeners.forEach(listener => listener());
  };
  return {
    getSnapshot: () => phase,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    set,
    claim: (expected: ReceiptFollowupPhase, next: ReceiptFollowupPhase) => {
      if (phase !== expected) return false;
      set(next);
      return true;
    },
  };
}

export type ForkRequest = { request_id: string; language: string; replace_guest_conversation_id?: string };
type ForkResponse = { conversation: { id: string }; created: boolean };
export const forkReceipt = (publicId: string, body: ForkRequest) => apiFetch<ForkResponse>(
  `/public/receipts/${encodeURIComponent(publicId)}/fork`, { method: 'POST', body: JSON.stringify(body) },
);
export async function runReceiptFork(intent: ReceiptFollowupIntent, accountId: string, fork = forkReceipt, replacementId?: string): Promise<ReceiptFollowupIntent> {
  if (intent.accountId && intent.accountId !== accountId) throw new Error('receipt_account_changed');
  if (intent.conversationId) return intent;
  const result = await fork(intent.publicId, {
    request_id: intent.requestId, language: intent.language,
    ...(replacementId ? { replace_guest_conversation_id: replacementId } : {}),
  });
  return { ...intent, accountId, conversationId: result.conversation.id };
}

/** Transport admission is not settlement. Reuse chat's durable lifecycle reader. */
export async function settleReceiptFollowup(intent: ReceiptFollowupIntent, dependencies: {
  load?: () => Promise<import('./argus-api').ApiMessage[]>;
  send: (text: string, options: import('@/components/chat/chat-send-selection').SendOptions) => Promise<boolean>;
  reconciliation?: Parameters<typeof resolveOrdinaryTransportAmbiguity>[3];
}): Promise<boolean> {
  if (!intent.conversationId) throw Error('receipt_followup_missing_destination');
  const load = dependencies.load ?? (() => loadAllConversationMessagePages(intent.conversationId!));
  const resolve = () => resolveOrdinaryTransportAmbiguity(load, new Set<string>(), intent.requestId, dependencies.reconciliation);
  const before = await resolve();
  if (before.kind === 'terminal') return true;
  // Unknown may be an unfamiliar recorded lifecycle. Only absence permits send.
  if (before.kind !== 'unknown' || before.items.some(message =>
    (message.metadata?.agent_runtime_turn as { request_id?: string } | undefined)?.request_id === intent.requestId,
  )) throw Error('receipt_followup_unsettled');
  let terminalSeen = false;
  if (dependencies.reconciliation?.signal?.aborted || !(await dependencies.send(intent.text, { requestId: intent.requestId, awaitCompletion: true, onTerminal: () => { terminalSeen = true; } }))) throw Error('receipt_followup_unsettled');
  if (terminalSeen) return false;
  if ((await resolve()).kind !== 'terminal') throw Error('receipt_followup_unsettled');
  return true;
}

/** A new session alone cannot adopt a pending send; verify the transferred copy. */
export async function bindReceiptFollowupAccount(intent: ReceiptFollowupIntent, accountId: string,
  load = loadAllConversationMessagePages,
): Promise<ReceiptFollowupIntent> {
  if (!intent.accountId || intent.accountId === accountId) return { ...intent, accountId };
  const claim = intent.guestClaim;
  if (!claim || claim.accountId !== accountId || (intent.conversationId && intent.conversationId !== claim.conversationId)) throw Error('receipt_account_changed');
  const items = await load(claim.conversationId);
  if (!items.some(message => {
    const shared = message.metadata?.shared_conversation as { request_id?: string; public_id?: string } | undefined;
    return shared?.request_id === intent.requestId && shared?.public_id === intent.publicId;
  })) throw Error('receipt_account_changed');
  const bound = { ...intent }; delete bound.guestClaim;
  return { ...bound, accountId, conversationId: claim.conversationId };
}
