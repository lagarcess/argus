import { test, expect, login } from './fixtures';

test('expired assistant export clears loaded household answers', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: 'Ask Clara', exact: true }).click();
  const drawer = page.getByRole('dialog');
  await drawer.getByRole('button', { name: 'See my net worth', exact: true }).click();
  await expect(drawer.locator('.ca-answer .ca-fact')).not.toHaveCount(0);
  await page.route('**/api/platform/assistant/conversations/*/export', route =>
    route.fulfill({ status: 401, json: { code: 'authentication_required' } }),
  );
  await drawer.getByRole('button', { name: 'Download local snapshot (JSON)', exact: true }).click();
  await expect(page.locator('.p-login')).toBeVisible();
  await expect(page.locator('.ca-drawer')).toHaveCount(0);
  await expect(page.locator('.ca-answers')).toHaveCount(0);
});
