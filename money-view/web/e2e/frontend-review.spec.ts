import { test, expect, login, navigate, read, screenshot, openProfile } from './fixtures';
import type { Page } from '@playwright/test';

async function signOut(page: Page) {
  await openProfile(page);
  await page.getByRole('dialog').getByRole('button', { name: /^(Sign out|Cerrar sesión)$/ }).click();
  await expect(page.getByRole('button', { name: /^(Sign in|Iniciar sesión)$/ })).toBeVisible();
}
async function createSavedDeposit(page: Page) {
  await navigate(page, 'deposits');
  await page.getByRole('button', { name: 'Review amount and horizon' }).click();
  await page.getByTestId('confirm-comparison').filter({ visible: true }).click();
  await page.getByRole('button', { name: 'Save comparison', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Comparison saved', exact: true })).toBeVisible();
}
async function publish(page: Page, scenario: string) {
  await page.getByTestId('demo-scenario').selectOption(scenario);
  const response = page.waitForResponse(response => response.url().endsWith('/api/demo/events') && response.request().method() === 'POST');
  await page.getByTestId('publish-demo-event').click();
  const receipt = await (await response).json();
  await expect.poll(async () => (await read(page, `/jobs/${receipt.job_id}`)).status).toBe('succeeded');
  await expect(page.getByTestId('publish-demo-event')).toBeEnabled();
  return receipt;
}

for (const role of ['editor', 'viewer'] as const) {
  test(`new ${role} signs in using the copied local ID and retains role boundaries`, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await login(page);
    const initial = await read(page, '/session');
    await navigate(page, 'household');
    const dialog = page.getByRole('dialog');
    await page.getByRole('button', { name: 'Edit name', exact: true }).click();
    await dialog.getByLabel('Name', { exact: true }).fill('   ');
    await dialog.getByRole('button', { name: 'Save changes' }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue('   ');
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Add demo member', exact: true }).click();
    await dialog.getByLabel('Name', { exact: true }).fill('   ');
    await dialog.getByLabel('Local password', { exact: false }).fill('Browser-member-2026!');
    await dialog.getByRole('combobox', { name: 'Role', exact: true }).selectOption(role);
    await dialog.getByRole('button', { name: 'Save changes' }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue('   ');
    await expect(dialog.getByLabel('Local password', { exact: false })).toHaveValue('Browser-member-2026!');
    await dialog.getByLabel('Name', { exact: true }).fill(`Browser ${role}`);
    await dialog.getByRole('button', { name: 'Save changes' }).click();
    await expect(dialog).toHaveCount(0);
    const receipt = page.getByRole('region', { name: 'Local account created' });
    const id = await receipt.getByLabel('Local login ID', { exact: true }).inputValue();
    await receipt.getByRole('button', { name: 'Copy login ID' }).click();
    await expect(receipt.getByRole('status')).toHaveText('Login ID copied.');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(id);
    await screenshot(page, `en-created-${role}-receipt`);
    await signOut(page);
    await page.getByRole('button', { name: /^(Sign in|Iniciar sesión)$/ }).click();
    await page.getByRole('button', { name: 'Usar un identificador local' }).click();
    await page.getByLabel('Identificador de cuenta local', { exact: false }).fill(id);
    await page.getByLabel('Contraseña local', { exact: false }).fill('Incorrect-member-password');
    await page.getByRole('button', { name: 'Abrir espacio' }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    await page.getByRole('button', { name: 'Perfiles demo', exact: true }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    await page.getByRole('button', { name: 'Usar un identificador local' }).click();
    await expect(page.getByLabel('Identificador de cuenta local', { exact: false })).toHaveValue(id);
    await expect(page.getByLabel('Contraseña local', { exact: false })).toHaveValue('Incorrect-member-password');
    await page.getByLabel('Contraseña local', { exact: false }).fill('Browser-member-2026!');
    await page.getByRole('button', { name: 'Abrir espacio' }).click();
    await expect(page.locator('.p-main h1')).toBeVisible();
    const member = await read(page, '/session');
    expect(member.user.id).toBe(id);
    expect(member.household.id).toBe(initial.household.id);
    expect(member.household.role).toBe(role);
    expect((await read(page, '/transactions?limit=25')).total).toBeGreaterThanOrEqual(12000);
    await navigate(page, 'accounts');
    await page.getByRole('button', { name: 'Agregar cuenta', exact: true }).click();
    await dialog.getByLabel('Nombre', { exact: true }).fill(`Local ${role} account`);
    await dialog.getByLabel('Institución', { exact: true }).fill('Local fixture');
    await dialog.getByRole('button', { name: 'Guardar', exact: true }).click();
    if (role === 'viewer') await expect(dialog.getByRole('alert')).toBeVisible();
    else {
      await expect(dialog).toHaveCount(0);
      expect((await read(page, '/accounts')).items.some((item: {name:string}) => item.name === `Local ${role} account`)).toBe(true);
    }
  });
}

test('real session revocation through another client makes CSV export remove private UI', async ({ page, playwright }) => {
  await login(page);
  await navigate(page, 'transactions');
  await expect(page.locator('tbody tr')).toHaveCount(25);
  const other = await playwright.request.newContext({ baseURL: 'http://127.0.0.1:5192' });
  try {
    expect((await other.post('/api/platform/session/login', { data: { user_id: 'user-demo', password: 'Clara-demo-2026!' } })).ok()).toBe(true);
    expect((await other.post('/api/platform/settings/sessions/revoke', { data: { scope: 'others' } })).ok()).toBe(true);
    const response = page.waitForResponse(response => response.url().includes('/transactions/export.csv'));
    await page.getByRole('button', { name: 'Export CSV', exact: true }).click();
    expect((await response).status()).toBe(401);
    await expect(page.getByRole('button', { name: /^(Sign in|Iniciar sesión)$/ })).toBeVisible();
    await expect(page.locator('.p-main')).toHaveCount(0);
    await expect(page.locator('tbody tr')).toHaveCount(0);
  } finally { await other.dispose(); }
});

test('notice selected while compute is pending hydrates its before and after record', async ({ page }) => {
  await login(page);
  await createSavedDeposit(page);
  await publish(page, 'leader_changed');
  await page.getByRole('button', { name: 'Change assumptions', exact: true }).click();
  await page.getByRole('button', { name: 'Review amount and horizon' }).click();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let observed!: () => void;
  const intercepted = new Promise<void>(resolve => { observed = resolve; });
  await page.route('**/api/confirmations/*/compute', async route => {
    observed(); await gate; await route.continue();
  });
  try {
    await page.getByTestId('confirm-comparison').filter({ visible: true }).click();
    await intercepted;
    await page.getByRole('button', { name: /^Notices/ }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'A deposit comparison has a new leader' }).click();
    await expect(page).toHaveURL(/decision=.*notice=/);
    release();
    await expect(page.getByTestId('saved-detail')).toBeVisible();
    await expect(page.getByTestId('saved-detail')).toContainText(/Before|After/);
    await screenshot(page, 'en-pending-compute-notice');
  } finally { release(); await page.unroute('**/api/confirmations/*/compute'); }
});

test('an invalid deposit target requests once and remains recoverable', async ({ page }) => {
  await login(page);
  let requests = 0;
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/decisions/missing-review-target') requests++; });
  const missing = page.waitForResponse(response => response.url().endsWith('/api/decisions/missing-review-target'));
  await page.goto('/#deposits?decision=missing-review-target');
  expect((await missing).status()).toBe(404);
  await expect(page.getByRole('alert')).toBeVisible();
  await page.getByRole('button', { name: /^Notices/ }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('alert')).toBeVisible();
  expect(requests).toBe(1);
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Review amount and horizon' })).toBeVisible();
});

test('a saved deposit refresh settles when another tab publishes a newer source load', async ({ page, context }) => {
  await login(page);
  await createSavedDeposit(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let observed!: () => void;
  const intercepted = new Promise<void>(resolve => { observed = resolve; });
  await page.route('**/api/platform/jobs/*', async route => {
    observed(); await gate; await route.continue();
  });
  const other = await context.newPage();
  try {
    await page.getByTestId('demo-scenario').selectOption('same_winner');
    const accepted = page.waitForResponse(response => response.url().endsWith('/api/demo/events') && response.request().method() === 'POST');
    await page.getByTestId('publish-demo-event').click();
    const first = await (await accepted).json();
    await intercepted;
    await expect(page.getByTestId('publish-demo-event')).toBeDisabled();
    await expect.poll(async () => (await read(page, `/jobs/${first.job_id}`)).status).toBe('succeeded');
    await other.goto('/#deposits');
    const second = await publish(other, 'leader_changed');
    expect(second.load_id).not.toBe(first.load_id);
    const homeResponse = await page.request.get('/api/home');
    expect(homeResponse.ok()).toBe(true);
    expect((await homeResponse.json()).source_status.load_id).toBe(second.load_id);
    release();
    await expect(page.getByTestId('publish-demo-event')).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Comparison saved', exact: true })).toBeVisible();
    await page.getByRole('button', { name: /^Notices/ }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'A deposit comparison has a new leader' }).click();
    await expect(page.getByTestId('saved-detail')).toBeVisible();
    await expect(page.getByTestId('saved-detail')).toContainText('Before');
    await expect(page.getByTestId('saved-detail')).toContainText('After');
    await screenshot(page, 'en-overlapping-source-loads');
  } finally {
    release();
    await page.unroute('**/api/platform/jobs/*');
    await other.close();
  }
});
