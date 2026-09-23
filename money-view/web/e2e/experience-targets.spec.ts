import { test, expect, login, navigate, read, openSettingsPanel, screenshot } from './fixtures';

test('exact transaction recall cancels stale targets and close removes the target', async ({ page }) => {
  await login(page);
  const eur = await read(page, '/transactions?currency=EUR&limit=1');
  const first = (await read(page, `/transactions?currency=EUR&limit=1&offset=${eur.total - 1}`)).items[0];
  const second = (await read(page, '/transactions?currency=USD&limit=1')).items[0];
  await navigate(page, 'transactions');
  await page.goto(`/#transactions?record_id=${first.id}`);
  const detail = page.getByRole('dialog');
  await expect(detail).toContainText(first.merchant);
  await expect(detail).toContainText('EUR');
  await page.keyboard.press('Escape');
  await expect(page).not.toHaveURL(/record_id=/);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let observed!: () => void;
  const intercepted = new Promise<void>(resolve => { observed = resolve; });
  await page.route(`**/api/platform/transactions/${first.id}`, async route => { observed(); await gate; await route.continue(); });
  try {
    await page.goto(`/#transactions?record_id=${first.id}`);
    await intercepted;
    await page.goto(`/#transactions?record_id=${second.id}`);
    await expect(detail).toContainText(second.merchant);
    await expect(detail.getByLabel('Description', { exact: true })).toHaveValue(second.description);
    release();
    await page.getByRole('dialog').getByLabel('Notes', { exact: true }).focus();
    await expect(detail.getByLabel('Description', { exact: true })).toHaveValue(second.description);
    await expect(page).toHaveURL(new RegExp(`record_id=${second.id}`));
    await screenshot(page, 'en-exact-transaction-target');
    await page.keyboard.press('Escape');
    await expect(detail).toHaveCount(0);
    await expect(page).not.toHaveURL(/record_id=/);
    await page.reload();
    await expect(page.locator('tbody tr')).toHaveCount(25);
    await expect(detail).toHaveCount(0);
  } finally { release(); await page.unroute(`**/api/platform/transactions/${first.id}`); }
});

test('historical budget recall owns its month and ignores a superseded target', async ({ page }) => {
  await login(page);
  await navigate(page, 'budgets');
  const budgets = [];
  for (const month of ['2024-01', '2024-02']) {
    await page.getByRole('button', { name: 'Create budget', exact: true }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox', { name: 'Category', exact: true }).selectOption('shopping');
    await dialog.getByLabel('Currency', { exact: true }).fill('EUR');
    await dialog.getByLabel('Month', { exact: true }).fill(month);
    await dialog.getByLabel('Limit', { exact: false }).fill('150');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    budgets.push((await read(page, `/budgets?month=${month}`)).items.find((item: {category:string,currency:string}) => item.category === 'shopping' && item.currency === 'EUR'));
  }
  const [first, second] = budgets;
  await page.goto(`/#budgets?record_id=${first.id}&month=2026-09`);
  await expect(page.getByLabel('Month', { exact: true })).toHaveValue(first.month);
  await expect(page.locator(`[data-record-id="${first.id}"]`)).toBeFocused();
  await expect(page.locator(`[data-record-id="${first.id}"]`)).toContainText('EUR');
  await page.goto('/#budgets');
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let observed!: () => void;
  const intercepted = new Promise<void>(resolve => { observed = resolve; });
  await page.route(`**/api/platform/budgets/${first.id}`, async route => { observed(); await gate; await route.continue(); });
  try {
    await page.goto(`/#budgets?record_id=${first.id}`);
    await intercepted;
    await page.goto(`/#budgets?record_id=${second.id}`);
    await expect(page.getByLabel('Month', { exact: true })).toHaveValue(second.month);
    release();
    await expect(page.locator(`[data-record-id="${second.id}"]`)).toBeFocused();
    await expect(page.getByLabel('Month', { exact: true })).toHaveValue(second.month);
    await screenshot(page, 'en-historical-budget-target');
    await page.goto('/#budgets?record_id=missing-browser-budget&month=2026-09');
    await expect(page.getByRole('alert')).toBeVisible();
    await page.getByRole('button', { name: 'View current budgets', exact: true }).click();
    await expect(page).not.toHaveURL(/record_id=/);
    const bills = (await read(page, '/bills')).items;
    expect(bills.length).toBeGreaterThan(0);
    await page.goto(`/#budgets?record_id=${bills[0].id}`);
    await expect(page.locator(`[data-record-id="${bills[0].id}"]`)).toBeFocused();
  } finally { release(); await page.unroute(`**/api/platform/budgets/${first.id}`); }
});

test('mobile settings Back and Forward restore the route and one focused overlay', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await navigate(page, 'settings');
  await openSettingsPanel(page, 'privacy');
  await expect(page.getByRole('dialog', { name: 'Privacy', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Privacy', exact: true })).toBeFocused();
  await page.goForward();
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await expect(page.getByRole('dialog', { name: 'Privacy', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Privacy', exact: true })).toBeFocused();
  await page.getByRole('button', { name: /Back to settings/ }).click();
  await expect(page.getByRole('navigation', { name: 'Settings sections' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: /^Help and information/ })).toBeFocused();
  await screenshot(page, 'en-390-settings-back');
});
