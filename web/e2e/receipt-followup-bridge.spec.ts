import { expect, test, type Page, type Route } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { installMobileShellFixture } from './support/mobile-shell-fixture';
import { backtestTurn } from '../__tests__/fixtures/receipt-turns';

const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
async function installBridge(page: Page, { account = 'guest', existing = false, unavailable = false, signedOut = false, retry = false, streamGate, rejectFirstSend = false, admitBeforeGate = false }: {
  account?: 'guest' | 'registered'; existing?: boolean; unavailable?: boolean; signedOut?: boolean; retry?: boolean;
  streamGate?: Promise<void>; rejectFirstSend?: number | false; admitBeforeGate?: boolean;
} = {}) {
  await installMobileShellFixture(page, { account, language: 'en', theme: 'dark' });
  const requestId = randomUUID();
  const receiver = randomUUID();
  const date = '2026-09-14T20:00:00Z';
  const intent = { publicId: 'public-shared-receipt', text: 'Change it to $300', language: 'en', requestId };
  await page.addInitScript(intent => {
    if (!window.sessionStorage.getItem('bridge-test-seeded')) {
      window.sessionStorage.setItem('argus:receipt-followup:v1', JSON.stringify(intent));
      window.sessionStorage.setItem('bridge-test-seeded', 'true');
    }
  }, intent);
  const calls = { fork: [] as Record<string, unknown>[], sends: [] as Record<string, unknown>[], creates: 0, bootstrap: 0 };
  let bootstrapped = !signedOut;
  let created = false;
  const conversation = { id: receiver, conversation_id: receiver, title: 'New conversation', pinned: false, created_at: date, updated_at: date };
  const messages: Record<string, unknown>[] = [
    { id: randomUUID(), conversation_id: receiver, role: 'user', content: 'What if I invested $250 each month in AAPL?', created_at: date, metadata: { shared_conversation: { snapshot_at: date, request_id: requestId, public_id: intent.publicId } } },
    { id: randomUUID(), conversation_id: receiver, role: 'assistant', content: 'ordinary-history-facts', created_at: date, metadata: { shared_conversation: { snapshot_at: date, request_id: requestId, public_id: intent.publicId, card: { ...backtestTurn, owner_note: null } } } },
  ];
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith('/me') && !bootstrapped) return json(route, { code: 'unauthorized' }, 401);
    if (path.endsWith('/auth/guest')) { calls.bootstrap++; bootstrapped = true; return json(route, { authenticated: true, reused: false, account_kind: 'guest' }); }
    if (path.endsWith('/fork')) {
      const body = request.postDataJSON(); calls.fork.push(body);
      if (unavailable) return json(route, { code: 'receipt_unavailable' }, 410);
      if (retry && calls.fork.length === 1) return route.abort('failed');
      if (existing && !body.replace_guest_conversation_id) return json(route, { code: 'receipt_guest_choice_required' }, 409);
      const first = !created; created = true;
      return json(route, { conversation, created: first });
    }
    if (path.endsWith('/conversations') && request.method() === 'POST') { calls.creates++; return json(route, { conversation }); }
    if (path === `/api/v1/conversations/${receiver}/messages`) return json(route, { items: messages, next_cursor: null });
    if (path === `/api/v1/conversations/${receiver}`) return json(route, conversation);
    if (path === '/api/v1/chat/stream') {
      const body = request.postDataJSON(); calls.sends.push({ ...body, request_id: request.headers()['x-request-id'] });
      if (rejectFirstSend && calls.sends.length === 1) return json(route, { code: 'rate_limited' }, rejectFirstSend);
      const turnId = randomUUID();
      const runtime = { request_id: request.headers()['x-request-id'], turn_id: turnId, status: 'running' };
      if (admitBeforeGate) messages.push({ id: turnId, conversation_id: receiver, role: 'user', content: body.message, metadata: { agent_runtime_turn: runtime }, created_at: date });
      if (streamGate) await streamGate;
      runtime.status = 'completed';
      const confirmation = { kind: 'backtest', confirmation_id: randomUUID(), confirmation_state: 'active', title: 'Ready to test', status: 'ready_to_run', status_label: 'Ready', rows: [{ key: 'contribution', label: 'Monthly contribution', value: '$300' }], actions: [{ id: 'run', type: 'run_backtest', label: 'Run test' }] };
      const answer = calls.sends.length === 1 ? 'Your own monthly test is ready.' : 'This is your follow-up.';
      const assistantId = randomUUID();
      if (!admitBeforeGate) messages.push({ id: turnId, conversation_id: receiver, role: 'user', content: body.message, metadata: { agent_runtime_turn: runtime }, created_at: date });
      messages.push( { id: assistantId, conversation_id: receiver, role: 'assistant', content: answer, metadata: { agent_runtime_turn: runtime, ...(calls.sends.length === 1 ? { confirmation_card: confirmation } : {}) }, created_at: date });
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'final', payload: { conversation_id: receiver, message_id: assistantId, assistant_response: answer, ...(calls.sends.length === 1 ? { confirmation } : {}) } })}\n\ndata: [DONE]\n\n` });
    }
    return route.fallback();
  });
  return { calls, requestId, receiver };
}

for (const account of ['guest', 'registered'] as const) {
  test(`${account} first follow-up hydrates frozen cards then sends once in own chat`, async ({ page }) => {
    const { calls, requestId, receiver } = await installBridge(page, { account, signedOut: account === 'guest' });
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Ready to test', exact: true })).toBeVisible();
    await expect(page.getByText('$300', { exact: true })).toBeVisible();
    await expect(page.getByText('From a shared conversation', { exact: false })).toHaveCount(2);
    await expect(page.locator('[data-receipt-card] input')).toHaveCount(0);
    expect(calls.fork).toHaveLength(1);
    expect(calls.fork[0].request_id).toBe(requestId);
    expect(calls.creates).toBe(0);
    expect(calls.bootstrap).toBe(account === 'guest' ? 1 : 0);
    expect(calls.sends).toHaveLength(1);
    expect(calls.sends[0].conversation_id).toBe(receiver);
    expect(calls.sends[0].request_id).toBe(requestId);
    await page.getByTestId('chat-input').fill('Tell me more');
    await page.getByTestId('chat-send').click();
    await expect(page.getByText('This is your follow-up.', { exact: true })).toBeVisible();
    expect(calls.sends).toHaveLength(2);
    expect(calls.fork).toHaveLength(1);
    await page.reload();
    await expect(page.getByText('This is your follow-up.', { exact: true })).toBeVisible();
    expect(calls.sends).toHaveLength(2);
  });
}

test('existing guest cancels without replacing or sending', async ({ page }) => {
  const { calls } = await installBridge(page, { existing: true });
  await page.goto('/chat');
  const dialog = page.getByRole('dialog', { name: 'Start a new conversation?' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(calls.fork).toHaveLength(1);
  expect(calls.creates).toBe(0);
  expect(calls.sends).toHaveLength(0);
  await expect(page.getByTestId('chat-input')).toBeEnabled();
});

test('existing guest explicit start over keeps fork request identity', async ({ page }) => {
  const { calls, requestId } = await installBridge(page, { existing: true });
  await page.goto('/chat');
  await page.getByRole('dialog').getByRole('button', { name: 'Start over', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ready to test', exact: true })).toBeVisible();
  expect(calls.fork).toHaveLength(2);
  expect(calls.fork.every(call => call.request_id === requestId)).toBe(true);
  expect(calls.fork[1].replace_guest_conversation_id).toBe('conversation-alpha');
  expect(calls.sends).toHaveLength(1);
});

test('transport retry reuses one request', async ({ page }) => {
  const { calls, requestId } = await installBridge(page, { retry: true });
  await page.goto('/chat');
  await page.getByRole('button', { name: /Try again|Retry/, exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ready to test', exact: true })).toBeVisible();
  expect(calls.fork).toHaveLength(2);
  expect(calls.fork.every(call => call.request_id === requestId)).toBe(true);
  expect(calls.sends).toHaveLength(1);
});

test('revoked shared link shows a refusal and creates no conversation or send', async ({ page }) => {
  const { calls } = await installBridge(page, { unavailable: true });
  await page.goto('/chat');
  await expect(page.getByRole('alert')).toBeVisible();
  expect(calls.creates).toBe(0);
  expect(calls.sends).toHaveLength(0);
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByTestId('chat-input')).toBeEnabled();
});

test('existing guest conversion opens the normal account dialog and preserves pending follow-up', async ({ page }) => {
  const { calls } = await installBridge(page, { existing: true });
  await page.goto('/chat');
  await page.getByRole('dialog').getByRole('button', { name: 'Sign in to keep it', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Email address', exact: true })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Start a new conversation?' })).toBeVisible();
  expect(calls.sends).toHaveLength(0);
  expect(calls.creates).toBe(0);
});

const savedFollowup = (page: Page) => page.evaluate(() => JSON.parse(window.sessionStorage.getItem('argus:receipt-followup:v1') ?? 'null'));
function deferredStream() { let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; }); return { gate, release }; }

test('pending follow-up survives delayed transport and clears only after final', async ({ page }) => {
  const delayed = deferredStream();
  const { calls, requestId, receiver } = await installBridge(page, { streamGate: delayed.gate });
  await page.goto('/chat');
  await expect.poll(() => calls.sends.length).toBe(1);
  expect(await savedFollowup(page)).toMatchObject({ requestId, conversationId: receiver, text: 'Change it to $300' });
  delayed.release();
  await expect.poll(() => savedFollowup(page)).toBeNull();
  expect(calls.fork).toHaveLength(1);
});

for (const refusal of [429, 404]) test(`pre-admission ${refusal} and reload reuse the original text request and fork`, async ({ page }) => {
  const { calls, requestId, receiver } = await installBridge(page, { rejectFirstSend: refusal });
  await page.goto('/chat');
  await expect(page.getByRole('button', { name: /Try again|Retry/, exact: true })).toBeVisible();
  expect(calls.sends).toHaveLength(1);
  expect(await savedFollowup(page)).toMatchObject({ requestId, conversationId: receiver, text: 'Change it to $300' });
  await page.reload();
  await expect.poll(() => savedFollowup(page)).toBeNull();
  expect(calls.fork).toHaveLength(1);
  expect(calls.sends).toHaveLength(2);
  expect(calls.sends.every(send => send.request_id === requestId && send.conversation_id === receiver && send.message === 'Change it to $300')).toBe(true);
});

test('reload of an admitted delayed turn reconciles without a second send', async ({ page }) => {
  const delayed = deferredStream();
  const { calls, requestId, receiver } = await installBridge(page, { streamGate: delayed.gate, admitBeforeGate: true });
  await page.goto('/chat');
  await expect.poll(() => calls.sends.length).toBe(1);
  expect(await savedFollowup(page)).toMatchObject({ requestId, conversationId: receiver });
  await page.reload();
  delayed.release();
  await expect.poll(() => savedFollowup(page)).toBeNull();
  expect(calls.fork).toHaveLength(1);
  expect(calls.sends).toHaveLength(1);
  await expect(page.getByRole('heading', { name: 'Ready to test', exact: true })).toBeVisible();
});

for (const destinationKnown of [true, false]) test(`verified guest handoff resumes retained fork with destination known=${destinationKnown}`, async ({ page }) => {
  const { calls, receiver, requestId } = await installBridge(page, { account: 'registered' });
  await page.addInitScript(({ receiver, destinationKnown }) => {
    const saved = JSON.parse(window.sessionStorage.getItem('argus:receipt-followup:v1')!);
    saved.accountId = 'former-guest';
    if (destinationKnown) saved.conversationId = receiver;
    saved.guestClaim = { accountId: 'mobile-shell-user', conversationId: receiver };
    window.sessionStorage.setItem('argus:receipt-followup:v1', JSON.stringify(saved));
  }, { receiver, destinationKnown });
  await page.goto('/chat');
  await expect.poll(() => savedFollowup(page)).toBeNull();
  expect(calls.fork).toHaveLength(0);
  expect(calls.sends).toHaveLength(1);
  expect(calls.sends[0]).toMatchObject({ request_id: requestId, conversation_id: receiver });
});

test('an unrelated account switch cannot replay the pending follow-up', async ({ page }) => {
  const { calls, receiver } = await installBridge(page, { account: 'registered' });
  await page.addInitScript(receiver => {
    const saved = JSON.parse(window.sessionStorage.getItem('argus:receipt-followup:v1')!);
    window.sessionStorage.setItem('argus:receipt-followup:v1', JSON.stringify({ ...saved, accountId: 'different-account', conversationId: receiver }));
  }, receiver);
  await page.goto('/chat');
  await expect(page.getByRole('button', { name: /Try again|Retry/, exact: true })).toBeVisible();
  expect(calls.fork).toHaveLength(0);
  expect(calls.sends).toHaveLength(0);
  expect(await savedFollowup(page)).not.toBeNull();
});
