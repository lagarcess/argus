import { z } from 'zod';
import { evidenceSchema } from '../../platform/types';
export const kinds = ['all', 'conversation', 'account', 'transaction', 'budget', 'goal', 'scenario', 'holding', 'deposit'] as const;
export type SearchKind = typeof kinds[number];
export type SearchScope = 'all' | 'recent' | 'pinned';
export const targetSchema = z.object({
    page: z.enum(['accounts', 'transactions', 'budgets', 'goals', 'scenarios', 'investments', 'deposits', 'saved', 'chat']),
    record_id: z.string(), conversation_id: z.string().nullable(), account_id: z.string().nullable(), decision: z.string().nullable(),
});
export const searchItemSchema = z.object({
    id: z.string(), kind: z.enum(kinds), title: z.string(), preview: z.string(), recorded_at: z.string().nullable(), as_of: z.string().nullable(), pinned: z.boolean(),
    target: targetSchema, fields: z.array(z.object({ label: z.string(), value: z.string() })), evidence: evidenceSchema.nullable(),
});
export type SearchItem = z.infer<typeof searchItemSchema>;
export const searchSchema = z.object({ items: z.array(searchItemSchema), has_more: z.boolean(), next_offset: z.number().nullable(), match_mode: z.literal('field_prefix'), query: z.string(), kind: z.enum(kinds), scope: z.enum(['all', 'recent', 'pinned']), deposit_window: z.number(), window_limited: z.boolean() });
export type SearchResponse = z.infer<typeof searchSchema>;
export function targetQuery(target: SearchItem['target']): Record<string, string> {
    const query: Record<string, string> = { record_id: target.record_id };
    if (target.conversation_id)
        query.conversation_id = target.conversation_id;
    if (target.account_id)
        query.account_id = target.account_id;
    if (target.decision)
        query.decision = target.decision;
    return query;
}
// Adapted from Argus useCommandPaletteKeys: one keyboard owner, no model call.
export function selectionIndex(current: number, key: string, length: number): number {
    if (!length)
        return -1;
    if (key === 'Home')
        return 0;
    if (key === 'End')
        return length - 1;
    if (key === 'ArrowDown')
        return Math.min(current + 1, length - 1);
    if (key === 'ArrowUp')
        return Math.max(current - 1, 0);
    return current;
}
