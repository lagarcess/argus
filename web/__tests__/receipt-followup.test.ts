import { describe, expect, test } from 'bun:test';
import { createReceiptFollowup, runReceiptFork } from '../lib/receipt-followup';

describe('receiver follow-up admission', () => {
  test('stores only the receiver text and public link with one retry identity', () => {
    const intent = createReceiptFollowup('public-link', ' Change it to $300 ', 'en');
    expect(intent.text).toBe('Change it to $300');
    expect(intent.requestId).toMatch(/^[0-9a-f-]{36}$/);
    expect(Object.keys(intent).sort()).toEqual(['language', 'publicId', 'requestId', 'text']);
  });
  test('empty follow-ups cannot create a fork', () => {
    expect(() => createReceiptFollowup('public-link', ' ', 'en')).toThrow();
  });
  test('retries use the same request, existing guests require explicit replacement', async () => {
    const intent = createReceiptFollowup('public-link', 'Why?', 'en');
    const calls: unknown[] = [];
    const fork = async (_id: string, body: unknown) => { calls.push(body); return { conversation: { id: 'receiver-chat' }, created: true }; };
    expect((await runReceiptFork(intent, 'receiver', fork)).conversationId).toBe('receiver-chat');
    await runReceiptFork(intent, 'receiver', fork, 'guest-chat');
    expect(calls).toEqual([
      { request_id: intent.requestId, language: 'en' },
      { request_id: intent.requestId, language: 'en', replace_guest_conversation_id: 'guest-chat' },
    ]);
  });
  test('an account switch cannot replay a bound pending intent', async () => {
    let called = false;
    const intent = { ...createReceiptFollowup('public-link', 'Why?', 'en'), accountId: 'first' };
    await expect(runReceiptFork(intent, 'second', async () => { called = true; throw Error(); })).rejects.toThrow('receipt_account_changed');
    expect(called).toBe(false);
  });
  test('already-forked follow-ups reuse their destination without a second fork', async () => {
    const intent = { ...createReceiptFollowup('public-link', 'Why?', 'en'), accountId: 'receiver', conversationId: 'fork' };
    expect(await runReceiptFork(intent, 'receiver', async () => { throw Error('must not fork'); })).toEqual(intent);
  });
});
