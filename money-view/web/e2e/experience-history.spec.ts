import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, login, navigate, openSettingsPanel, read, screenshot, evidenceDirectory } from './fixtures';

test('mixed conversation history paginates, exports, restores and moves both sources to recently deleted', async ({ page }) => {
  await login(page);
  const seeded: Record<string, { id: string; title: string }[]> = { chat: [], assistant: [] };
  // Volume setup uses public canonical writers in this test's temporary database.
  // All recovery and bulk changes below are performed through the visible UI.
  for (const source of ['chat', 'assistant'] as const) {
    for (let index = 0; index < 21; index++) {
      const title = `Browser ${source === 'chat' ? 'current' : 'older'} history ${index + 1}`;
      const created = source === 'chat'
        ? await page.request.post('/api/platform/chat/conversations', { data: { title } })
        : await page.request.post('/api/platform/assistant/ask', { data: { action: 'net_worth', parameters: { currency: 'USD' }, locale: 'en' } });
      expect(created.ok(), `${source} fixture create ${created.status()}: ${created.ok() ? '' : await created.text()}`).toBe(true);
      const body = await created.json();
      const id = source === 'chat' ? body.id : body.conversation_id;
      expect(typeof id).toBe('string');
      const archived = await page.request.patch(`/api/platform/${source}/conversations/${id}`, { data: { title, state: 'archived' } });
      expect(archived.ok()).toBe(true);
      seeded[source].push({ id, title });
    }
  }
  writeFileSync(join(evidenceDirectory, 'mixed-history-fixture-provenance.json'), JSON.stringify({ setup: 'Public local API only; 21 rows per source to cross the 20-row page boundary', current_writer: 'POST /api/platform/chat/conversations', older_writer: 'POST /api/platform/assistant/ask with typed net_worth action', provider_keys: 'empty', records: seeded }, null, 2));
  await navigate(page, 'settings');
  await page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: /^Data and personalization / }).click();
  await page.locator('.settings-section-detail').getByRole('button', { name: 'Archived conversations', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const groups = { chat: dialog.getByRole('region', { name: 'Current conversations', exact: true }), assistant: dialog.getByRole('region', { name: 'Older conversations', exact: true }) };
  for (const source of ['chat', 'assistant'] as const) {
    const group = groups[source];
    await expect(group.getByRole('article')).toHaveCount(20);
    await expect(group.getByRole('status').filter({ hasText: /of \d+ conversations/ })).toContainText('1–20 of 21');
    await group.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(group.getByRole('article')).toHaveCount(1);
    if (source === 'chat') await expect(groups.assistant.getByRole('article')).toHaveCount(20);
    await expect(group.getByRole('status').filter({ hasText: /of \d+ conversations/ })).toContainText('21–21 of 21');
    await expect(group.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
    const title = await group.getByRole('article').locator('strong').innerText();
    const expected = seeded[source].find(row => row.title === title)!;
    expect(expected).toBeTruthy();
    const download = page.waitForEvent('download');
    await group.getByRole('button', { name: 'Export JSON', exact: true }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe(`argus-${source}-conversation.json`);
    const exported = JSON.parse(readFileSync((await file.path())!, 'utf8'));
    expect(exported.local_only).toBe(true);
    expect(exported.conversation.id).toBe(expected.id);
    expect(exported.conversation.title).toBe(title);
    if (source === 'assistant') expect(exported.messages.length).toBeGreaterThan(0);
    await group.getByRole('button', { name: 'Restore', exact: true }).click();
    await expect(group.getByRole('article')).toHaveCount(20);
    await expect(group.getByRole('status').filter({ hasText: /of \d+ conversations/ })).toContainText('1–20 of 20');
    expect((await read(page, `/${source}/conversations?state=active&limit=100`)).items.map((row: { id: string }) => row.id)).toContain(expected.id);
  }
  await screenshot(page, 'en-mixed-history-restored');
  await page.keyboard.press('Escape');
  await openSettingsPanel(page, 'data');
  await expect(dialog).toContainText('Current conversations');
  await expect(dialog).toContainText('Older conversations');
  await expect(dialog).toContainText('Actions and receipts');
  const settings = await read(page, '/settings');
  await dialog.getByRole('button', { name: 'Move all history to recently deleted', exact: true }).click();
  await dialog.getByLabel('Confirm the name', { exact: false }).fill(settings.household.name);
  await dialog.getByLabel('Type TRASH HOUSEHOLD CONVERSATIONS to confirm', { exact: true }).fill('TRASH HOUSEHOLD CONVERSATIONS');
  const moved = page.waitForResponse(response => response.url().endsWith('/settings/history/trash-all'));
  await dialog.getByRole('button', { name: 'Move all to recently deleted', exact: true }).click();
  const receipt = await moved;
  expect(receipt.ok()).toBe(true);
  expect((await receipt.json()).counts).toEqual({ chat: 21, assistant: 21 });
  await page.keyboard.press('Escape');
  await page.locator('.settings-section-detail').getByRole('button', { name: 'Recently deleted', exact: true }).click();
  for (const source of ['chat', 'assistant'] as const) {
    await expect(groups[source].getByRole('article')).toHaveCount(20);
    await expect(groups[source].getByRole('status').filter({ hasText: /of \d+ conversations/ })).toContainText('1–20 of 21');
    expect((await read(page, `/${source}/conversations?state=active`)).total).toBe(0);
    expect((await read(page, `/${source}/conversations?state=archived`)).total).toBe(0);
    expect((await read(page, `/${source}/conversations?state=trashed`)).total).toBe(21);
  }
  await screenshot(page, 'en-mixed-history-recently-deleted');
  await page.reload();
  await expect(dialog.getByRole('region', { name: 'Current conversations', exact: true }).getByRole('article')).toHaveCount(20);
  await expect(dialog.getByRole('region', { name: 'Older conversations', exact: true }).getByRole('article')).toHaveCount(20);
});
