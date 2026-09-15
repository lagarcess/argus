import { apiFetch } from './argus-api-transport';
import { readSessionStored, writeSessionStored, removeSessionStored } from './browser-storage';
import { randomId } from './random-id';

const KEY = 'argus:receipt-followup:v1';
export type ReceiptFollowupIntent = {
  publicId: string; text: string; language: string; requestId: string;
  accountId?: string; conversationId?: string;
};
export function createReceiptFollowup(publicId: string, text: string, language: string): ReceiptFollowupIntent {
  if (!text.trim()) throw new Error('receipt_empty_followup');
  return { publicId, text: text.trim(), language, requestId: randomId() };
}
export function saveReceiptFollowup(intent: ReceiptFollowupIntent): boolean {
  return writeSessionStored(KEY, JSON.stringify(intent));
}
export function readReceiptFollowup(): ReceiptFollowupIntent | null {
  try {
    const intent = JSON.parse(readSessionStored(KEY) ?? 'null');
    return intent && ['publicId', 'text', 'language', 'requestId'].every(key => typeof intent[key] === 'string' && intent[key].trim()) ? intent : null;
  } catch { return null; }
}
export function clearReceiptFollowup() { removeSessionStored(KEY); }
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
