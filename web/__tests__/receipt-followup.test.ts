import { describe, expect, test } from 'bun:test';
import { createReceiptFollowup, runReceiptFork, settleReceiptFollowup, bindReceiptFollowupAccount, createReceiptFollowupLifecycle } from '../lib/receipt-followup';

test('queued hydration effects cannot send again after rejection or completion', () => {
  for (const outcome of ['error', 'done'] as const) {
    const lifecycle = createReceiptFollowupLifecycle();
    let sends = 0;
    const effect = () => { if (lifecycle.claim('hydrating', 'working')) sends++; };
    lifecycle.set('hydrating');
    effect();
    // Render effects may have captured hydrating before this promise settles.
    lifecycle.set(outcome);
    effect();
    expect(sends).toBe(1);
    expect(lifecycle.getSnapshot()).toBe(outcome);
    if (outcome === 'error') {
      expect(lifecycle.claim('error', 'working')).toBe(true);
      lifecycle.set('hydrating');
      effect();
      expect(sends).toBe(2);
    }
  }
});

test('the rendered phase reads the same owner that admits effects', () => {
  const lifecycle = createReceiptFollowupLifecycle();
  const rendered: string[] = [];
  const unsubscribe = lifecycle.subscribe(() => rendered.push(lifecycle.getSnapshot()));
  expect(lifecycle.claim('initial', 'working')).toBe(true);
  expect(lifecycle.claim('initial', 'working')).toBe(false);
  lifecycle.set('hydrating');
  expect(rendered).toEqual(['working', 'hydrating']);
  unsubscribe();
  lifecycle.set('done');
  expect(rendered).toHaveLength(2);
});

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

describe('durable follow-up settlement', () => {
  test('keeps the intent pending until the streamed turn is durably terminal', async () => {
    const intent = { ...createReceiptFollowup('link', 'Why?', 'en'), conversationId: 'fork' };
    let release!: () => void;
    let settled = false;
    let terminal = false;
    const gate = new Promise<void>(resolve => { release = resolve; });
    const operation = settleReceiptFollowup(intent, {
      load: async () => terminal ? terminalMessages(intent.requestId) : [],
      send: async () => { await gate; terminal = true; return true; },
    }).then(() => { settled = true; });
    await Promise.resolve(); await Promise.resolve();
    expect(settled).toBe(false);
    release(); await operation;
    expect(settled).toBe(true);
  });
  test('pre-admission failure preserves the same request for retry', async () => {
    const intent = { ...createReceiptFollowup('link', 'Why?', 'en'), conversationId: 'fork' };
    const sent: string[] = [];
    await expect(settleReceiptFollowup(intent, { load: async () => [], send: async (_text, options) => { sent.push(options.requestId!); return true; } })).rejects.toThrow('receipt_followup_unsettled');
    let admitted = false;
    await settleReceiptFollowup(intent, { load: async () => admitted ? terminalMessages(intent.requestId) : [], send: async (_text, options) => { sent.push(options.requestId!); admitted = true; return true; } });
    expect(sent).toEqual([intent.requestId, intent.requestId]);
  });
  test('reloading an admitted request reconciles without sending another turn', async () => {
    const intent = { ...createReceiptFollowup('link', 'Why?', 'en'), conversationId: 'fork' };
    let reads = 0;
    await settleReceiptFollowup(intent, { load: async () => terminalMessages(intent.requestId, reads++ ? 'completed' : 'running'), send: async () => { throw Error('must not send'); }, reconciliation: { followUpDelaysMs: [0], wait: async () => {} } });
    expect(reads).toBe(2);
  });
});

function terminalMessages(requestId: string, status = 'completed'): import('../lib/argus-api').ApiMessage[] {
  return [{ id: 'request-message', conversation_id: 'fork', role: 'user', content: 'Why?', created_at: '2026-09-14T20:00:00Z', metadata: { agent_runtime_turn: { request_id: requestId, turn_id: 'request-message', status } } }];
}

describe('verified guest handoff binding', () => {
  test('rebinds only the claimed destination containing this imported request', async () => {
    const intent = { ...createReceiptFollowup('link', 'Why?', 'en'), accountId: 'guest', conversationId: 'fork', guestClaim: { accountId: 'account', conversationId: 'fork' } };
    const bound = await bindReceiptFollowupAccount(intent, 'account', async () => [{ ...terminalMessages(intent.requestId)[0], metadata: { shared_conversation: { request_id: intent.requestId, public_id: intent.publicId } } }]);
    expect(bound.accountId).toBe('account'); expect(bound.conversationId).toBe('fork');
    expect(bound.guestClaim).toBeUndefined();
  });
  test('recovers a lost fork response using verified claim and imported request identity', async () => {
    const intent = { ...createReceiptFollowup('link', 'Why?', 'en'), accountId: 'guest', guestClaim: { accountId: 'account', conversationId: 'fork' } };
    const bound = await bindReceiptFollowupAccount(intent, 'account', async () => [{ ...terminalMessages(intent.requestId)[0], metadata: { shared_conversation: { request_id: intent.requestId, public_id: intent.publicId } } }]);
    expect(bound.conversationId).toBe('fork');
  });
  test('rejects unrelated accounts and claimed conversations without this request', async () => {
    const intent = { ...createReceiptFollowup('link', 'Why?', 'en'), accountId: 'guest', conversationId: 'fork', guestClaim: { accountId: 'account', conversationId: 'fork' } };
    await expect(bindReceiptFollowupAccount(intent, 'unrelated', async () => [])).rejects.toThrow('receipt_account_changed');
    await expect(bindReceiptFollowupAccount(intent, 'account', async () => [])).rejects.toThrow('receipt_account_changed');
  });
});
