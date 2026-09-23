import { test, expect, login, navigate } from './fixtures';

test('expired assistant export clears loaded household answers', async ({ page, playwright }) => {
  await login(page);
  await navigate(page, 'chat');
  await page.locator('[data-example-id="spending"]').click();
  await expect(page.locator('.argus-fact')).not.toHaveCount(0);
  const other = await playwright.request.newContext({ baseURL: 'http://127.0.0.1:5192' });
  try {
    expect((await other.post('/api/platform/session/login', { data: { user_id: 'user-demo', password: 'Clara-demo-2026!' } })).ok()).toBe(true);
    expect((await other.post('/api/platform/settings/sessions/revoke', { data: { scope: 'others' } })).ok()).toBe(true);
    await page.getByTestId('conversation-page').locator('summary[aria-label="Conversation actions"]').click();
    const response = page.waitForResponse(response => response.url().includes('/chat/conversations/') && response.url().endsWith('/export'));
    await page.getByRole('menuitem', { name: 'Download local copy', exact: true }).click();
    expect((await response).status()).toBe(401);
    await expect(page.getByRole('button', { name: /^(Sign in|Iniciar sesión)$/ })).toBeVisible();
    await expect(page.getByTestId('conversation-page')).toHaveCount(0);
    await expect(page.locator('.argus-fact')).toHaveCount(0);
  } finally { await other.dispose(); }
});
