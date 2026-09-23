import { test, expect, read, navigate } from './fixtures';
import { enterGuest } from './experience-helpers';

async function openTextConversation(page: import('@playwright/test').Page) {
  await enterGuest(page, 'en', 'demo');
  const created = await page.request.post('/api/platform/chat/conversations', { data: { title: 'Composer delivery regression' } });
  expect(created.ok()).toBe(true);
  const { id } = await created.json();
  const capabilities = await read(page, '/chat/capabilities');
  await page.route('**/api/platform/chat/capabilities', async route => {
    await route.fulfill({ json: { ...capabilities, model_available: true } });
  });
  await page.goto(`/#chat?conversation_id=${id}`);
  await expect(page.getByTestId('chat-input')).toBeVisible();
  return id as string;
}

function acceptedFrame(turnId: string, conversationId: string) {
  return `data: ${JSON.stringify({ type: 'final', turn_id: turnId, conversation_id: conversationId, status: 'completed', code: 'completed', message: null })}\n\ndata: [DONE]\n\n`;
}

function draftStored(page: import('@playwright/test').Page, text: string) {
  return page.evaluate(value => Object.entries(sessionStorage).some(([key, stored]) => key.startsWith('argus-chat-draft:v1:') && stored.includes(value)), text);
}

for (const kind of ['whitespace', 'multiline', 'mention'] as const) {
  test(`accepted inline retry clears ${kind} draft and storage`, async ({ page }) => {
    const conversationId = await openTextConversation(page);
    const input = page.getByTestId('chat-input');
    let expected: string;
    if (kind === 'whitespace') {
      await input.fill('ask about spending  ');
      expected = 'ask about spending';
    } else if (kind === 'multiline') {
      await input.fill('first line');
      await input.press('Shift+Enter');
      await page.keyboard.insertText('second line');
      expected = 'first line\nsecond line';
    } else {
      const account = (await read(page, '/chat/context')).accounts[0];
      expect(account).toBeTruthy();
      await input.fill(`Review @${account.name.slice(0, 3)}`);
      await page.getByRole('option').filter({ hasText: account.name }).first().click();
      expected = `Review @${account.name}`;
    }
    const turnIds: string[] = [];
    await page.route('**/api/platform/chat/turn', async route => {
      const payload = route.request().postDataJSON();
      expect(payload.text).toBe(expected);
      turnIds.push(payload.turn_id);
      if (turnIds.length === 1) await route.abort('connectionreset');
      else await route.fulfill({ status: 200, contentType: 'text/event-stream', body: acceptedFrame(payload.turn_id, conversationId) });
    });
    await page.getByTestId('chat-send').click();
    await expect(page.getByRole('alert')).toBeVisible();
    await page.getByRole('alert').getByRole('button', { name: 'Retry' }).click();
    await expect(page.getByTestId('chat-send')).toBeDisabled();
    await expect(input).toHaveText('');
    expect(turnIds).toHaveLength(2);
    expect(turnIds[1]).toBe(turnIds[0]);
    expect(await draftStored(page, expected)).toBe(false);
    await page.reload();
    await expect(page.getByTestId('chat-input')).toHaveText('');
  });
}

test('accepted ordinary send clears reload draft; typed action and newer edits preserve it', async ({ page }) => {
  const conversationId = await openTextConversation(page);
  const input = page.getByTestId('chat-input');
  await input.fill('Keep this draft');
  await page.route('**/api/platform/chat/turn', async route => {
    const payload = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: acceptedFrame(payload.turn_id, conversationId) });
  });
  await page.locator('[data-example-id="spending"]').click();
  await expect(input).toHaveText('Keep this draft');
  await input.fill('Send this draft');
  await page.getByTestId('chat-send').click();
  await expect(input).toHaveText('');
  expect(await draftStored(page, 'Send this draft')).toBe(false);
  await page.reload();
  await expect(page.getByTestId('chat-input')).toHaveText('');

  await input.fill('Older request');
  let attempts = 0;
  await page.unroute('**/api/platform/chat/turn');
  await page.route('**/api/platform/chat/turn', async route => {
    attempts += 1;
    const payload = route.request().postDataJSON();
    if (attempts === 1) await route.abort('connectionreset');
    else await route.fulfill({ status: 200, contentType: 'text/event-stream', body: acceptedFrame(payload.turn_id, conversationId) });
  });
  await page.getByTestId('chat-send').click();
  await expect(page.getByRole('alert')).toBeVisible();
  await input.fill('Newer draft');
  await page.getByRole('alert').getByRole('button', { name: 'Retry' }).click();
  await expect(input).toHaveText('Newer draft');
  await page.reload();
  await expect(page.getByTestId('chat-input')).toHaveText('Newer draft');
});

test('accepted staged handoff removes its saved draft record', async ({ page }) => {
  const conversationId = await openTextConversation(page);
  await navigate(page, 'overview');
  let attempts = 0;
  await page.route('**/api/platform/chat/turn', async route => {
    attempts += 1;
    const payload = route.request().postDataJSON();
    if (attempts === 1) await route.abort('connectionreset');
    else await route.fulfill({ status: 200, contentType: 'text/event-stream', body: acceptedFrame(payload.turn_id, conversationId) });
  });
  await page.getByTestId('chat-input').fill('Review my staged question');
  await page.getByTestId('chat-send').click();
  await expect(page.getByRole('alert')).toBeVisible();
  const draftId = new URLSearchParams(page.url().split('?')[1]).get('draft');
  expect(draftId).toBeTruthy();
  await page.getByRole('alert').getByRole('button', { name: 'Retry' }).click();
  await expect(page).toHaveURL(new RegExp(`conversation_id=${conversationId}`));
  expect(await page.evaluate(id => Object.keys(sessionStorage).some(key => key.endsWith(`:${id}`)), draftId)).toBe(false);
  await page.reload();
  await expect(page.getByTestId('chat-input')).toHaveText('');
});
