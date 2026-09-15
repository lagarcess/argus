import type { PublicReceiptPayload } from './public-receipt-contract';
import type { PublicReceiptTurn } from './public-receipt-turns';

export type SharedConversation = { snapshot_at: string; card?: PublicReceiptTurn | PublicReceiptPayload };
export function sharedConversationFromMetadata(metadata: Record<string, unknown>): SharedConversation | null {
  const value = metadata.shared_conversation;
  if (!value || typeof value !== 'object' || !('snapshot_at' in value) || typeof value.snapshot_at !== 'string') return null;
  return { snapshot_at: value.snapshot_at, ...('card' in value && value.card && typeof value.card === 'object' ? { card: value.card as PublicReceiptTurn | PublicReceiptPayload } : {}) };
}
