import { test, expect, read, navigate, screenshot } from './fixtures';
import { enterGuest } from './experience-helpers';

test('editing a proposal blocks confirmation until the revised target amount is saved', async ({ page }) => {
  await enterGuest(page, 'en', 'demo');
  const before = (await read(page, '/goals')).items;
  await navigate(page, 'chat');
  await page.locator('[data-example-id="sample-goal"]').click();
  const proposal = page.locator('[data-proposal-id][data-proposal-status="pending"]');
  await expect(proposal).toBeVisible();
  await proposal.getByRole('button', { name: 'Edit', exact: true }).click();
  await proposal.getByLabel('Target amount · DOP', { exact: true }).fill('12500');
  await expect(proposal.getByRole('button', { name: 'Confirm change', exact: true })).toHaveCount(0);
  expect((await read(page, '/goals')).items).toHaveLength(before.length);
  await screenshot(page, 'en-unsaved-proposal-confirm-guard');
  await proposal.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(proposal.getByRole('button', { name: 'Confirm change', exact: true })).toBeEnabled();
  await expect(proposal).toContainText('12,500');
  await proposal.getByRole('button', { name: 'Confirm change', exact: true }).click();
  await expect(page.locator('[data-receipt-id]')).toHaveCount(1);
  const existing = new Set(before.map((row: { id: string }) => row.id));
  const created = (await read(page, '/goals')).items.filter((row: { id: string }) => !existing.has(row.id));
  expect(created).toHaveLength(1);
  expect(Number(created[0].target_amount)).toBe(12500);
  expect(created[0].currency).toBe('DOP');
  await page.reload();
  await expect(page.locator('[data-receipt-id]')).toHaveCount(1);
});

test('changing conversations cancels older-message loading without disabling the new history', async ({ page }) => {
  await enterGuest(page, 'en', 'demo');
  const ids: string[] = [];
  for (const title of ['Browser first paged conversation', 'Browser second paged conversation']) {
    const created = await page.request.post('/api/platform/chat/conversations', { data: { title } });
    expect(created.ok()).toBe(true);
    const { id } = await created.json();
    ids.push(id);
    // Public typed read writer supplies a real 52-message pagination fixture.
    for (let index = 0; index < 26; index++) {
      const response = await page.request.post('/api/platform/chat/turn', { data: { conversation_id: id, turn_id: `browser-page-${id}-${index}`, locale: 'en', currency: 'DOP', action: { kind: 'read', action: 'spending', parameters: { currency: 'DOP' } } } });
      expect(response.ok()).toBe(true);
      expect(await response.text()).toMatch(/"status"\s*:\s*"completed"/);
    }
    expect((await read(page, `/chat/conversations/${id}?limit=50`)).total).toBe(52);
  }
  await page.goto(`/#chat?conversation_id=${ids[0]}`);
  await page.reload();
  const older = page.getByRole('button', { name: 'Load older', exact: true });
  await expect(older).toBeEnabled();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let arrived!: () => void;
  const pending = new Promise<void>(resolve => { arrived = resolve; });
  await page.route(`**/chat/conversations/${ids[0]}?limit=50&offset=50`, async route => {
    arrived();
    await gate;
    await route.continue().catch(() => {});
  });
  try {
    await older.click();
    await pending;
    await page.getByTestId('recent-conversations').locator(`[data-conversation-id="${ids[1]}"]`).getByRole('button').first().click();
    await expect(page.getByTestId('conversation-page').getByRole('heading', { name: 'Browser second paged conversation' })).toBeVisible();
    await expect(older).toBeEnabled();
    await older.click();
    await expect(page.getByTestId('chat-transcript').locator('[data-message-id]')).toHaveCount(52);
    release();
    await expect(page).toHaveURL(new RegExp(`conversation_id=${ids[1]}`));
    await expect(older).toHaveCount(0);
    await screenshot(page, 'en-older-history-route-recovery');
  } finally {
    release();
    await page.unroute(`**/chat/conversations/${ids[0]}?limit=50&offset=50`);
  }
});
