import { readSessionStored, writeSessionStored, removeSessionStored } from './browser-storage';
import { randomId } from './random-id';

const KEY = 'argus:receipt-followup:v1';
export type ReceiptFollowupIntent = {
  publicId: string; text: string; language: string; requestId: string;
  accountId?: string; conversationId?: string;
  /** Server-confirmed handoff, recorded only after the new auth session is installed. */
  guestClaim?: { accountId: string; conversationId: string };
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
export function clearReceiptFollowup(requestId?: string) {
  if (!requestId || readReceiptFollowup()?.requestId === requestId) removeSessionStored(KEY);
}

export function rememberReceiptFollowupClaim(accountId: string, claimedConversationId: string): void {
  const intent = readReceiptFollowup();
  if (!intent?.accountId || (intent.conversationId && intent.conversationId !== claimedConversationId)) return;
  saveReceiptFollowup({ ...intent, guestClaim: { accountId, conversationId: claimedConversationId } });
}

