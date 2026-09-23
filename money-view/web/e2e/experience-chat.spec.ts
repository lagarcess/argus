import { test, expect, navigate, read, screenshot, openProfile, login, openSettingsPanel } from './fixtures';
import { enterGuest } from './experience-helpers';

for (const language of ['en', 'es'] as const) {
  test(`${language}: guest proposal confirms once, opens its goal, and survives claim and recall`, async ({ page }) => {
    const en = language === 'en';
    const originalSession = await enterGuest(page, language, 'demo');
    const before = await read(page, '/goals');
    await navigate(page, 'chat');
    const preparedTurn = page.waitForResponse(response => response.url().endsWith('/api/platform/chat/turn'));
    await page.locator('[data-example-id="sample-goal"]').click();
    const prepared = await preparedTurn;
    expect(prepared.ok(), `proposal turn: ${prepared.status()} ${prepared.ok() ? '' : await prepared.text()}`).toBe(true);
    const proposal = page.locator('[data-proposal-id][data-proposal-status="pending"]');
    await expect(proposal).toHaveAttribute('data-proposal-status', 'pending');
    await expect(proposal).toContainText(en ? 'Nothing is saved until you confirm this change.' : 'Nada se guardará hasta que confirmes este cambio.');
    expect((await read(page, '/goals')).items).toHaveLength(before.items.length);
    await proposal.getByRole('button', { name: en ? 'Edit' : 'Editar', exact: true }).click();
    const goalName = `Browser ${language} confirmed reserve`;
    await proposal.getByLabel(en ? 'Name' : 'Nombre', { exact: true }).fill(goalName);
    await proposal.getByRole('button', { name: en ? 'Save changes' : 'Guardar cambios', exact: true }).click();
    await expect(proposal).toContainText(goalName);
    await expect(proposal).toContainText('DOP');
    const confirmed = page.waitForResponse(response => response.url().includes('/chat/proposals/') && response.url().endsWith('/confirm'));
    await proposal.getByRole('button', { name: en ? 'Confirm change' : 'Confirmar cambio', exact: true }).click();
    expect((await confirmed).ok()).toBe(true);
    const receipt = page.locator('[data-receipt-id]').first();
    await expect(receipt).toBeVisible();
    const receiptId = await receipt.getAttribute('data-receipt-id');
    const conversationURL = page.url();
    const saved = (await read(page, '/goals')).items.filter((goal: { name: string }) => goal.name === goalName);
    expect(saved).toHaveLength(1);
    expect(saved[0].currency).toBe('DOP');
    await screenshot(page, `${language}-proposal-receipt`);
    await receipt.getByRole('button', { name: en ? 'Open the saved record' : 'Abrir el registro guardado', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`#goals\\?.*record_id=${saved[0].id}`));
    await expect(page.getByRole('article').filter({ has: page.getByRole('heading', { name: goalName, exact: true }) })).toBeFocused();
    await page.goBack();
    await expect(page).toHaveURL(conversationURL);
    await page.reload();
    await expect(page.locator(`[data-receipt-id="${receiptId}"]`)).toBeVisible();
    expect((await read(page, '/goals')).items.filter((goal: { name: string }) => goal.name === goalName)).toHaveLength(1);

    await page.getByRole('button', { name: en ? 'Keep workspace' : 'Conservar espacio', exact: true }).click();
    const claim = page.getByRole('dialog', { name: en ? 'Keep your workspace' : 'Conservar tu espacio' });
    await claim.getByLabel(en ? 'Your name' : 'Tu nombre', { exact: true }).fill('Browser local owner');
    await claim.getByLabel(en ? 'Password' : 'Contraseña', { exact: false }).fill('Browser-claim-2026!');
    await claim.getByRole('button', { name: en ? 'Keep workspace' : 'Conservar espacio', exact: true }).click();
    const id = await claim.getByLabel(en ? 'Local account ID' : 'Identificador local', { exact: true }).inputValue();
    expect(id).toBe(originalSession.user.id);
    await claim.getByRole('button', { name: en ? 'Continue' : 'Continuar', exact: true }).click();
    const claimed = await read(page, '/session');
    expect(claimed.guest.is_guest).toBe(false);
    expect(claimed.household.id).toBe(originalSession.household.id);
    await openProfile(page);
    await page.getByRole('dialog').getByRole('button', { name: /^(Sign out|Cerrar sesión)$/ }).click();
    await page.getByRole('button', { name: /^(Sign in|Iniciar sesión)$/ }).click();
    await page.getByRole('button', { name: /^(Use a local account ID|Usar un identificador local)$/ }).click();
    await page.getByLabel(/^(Local account ID|Identificador de cuenta local)/).fill(id);
    await page.getByLabel(/^(Local password|Contraseña local)/).fill('Browser-claim-2026!');
    await page.getByRole('button', { name: /^(Open workspace|Abrir espacio)$/ }).click();
    await expect(page.locator('.p-topbar')).toBeVisible();
    await page.keyboard.press('ControlOrMeta+k');
    const search = page.getByRole('dialog', { name: en ? 'Search' : 'Buscar', exact: true });
    await search.getByRole('combobox', { name: en ? 'Search' : 'Buscar', exact: true }).fill(goalName);
    await expect(search.getByRole('listbox').getByRole('option').first()).toContainText(goalName);
    await search.getByRole('combobox', { name: en ? 'Search' : 'Buscar', exact: true }).press('Enter');
    await expect(page).toHaveURL(new RegExp(`#goals\\?.*record_id=${saved[0].id}`));
    expect((await read(page, '/goals')).items.filter((goal: { name: string }) => goal.name === goalName)).toHaveLength(1);
  });

  test(`${language}: keyless composer preserves draft, input semantics, navigation and attachment`, async ({ page }) => {
    const en = language === 'en';
    await page.setViewportSize({ width: 390, height: 844 });
    await enterGuest(page, language, 'demo');
    const goalsBefore = (await read(page, '/goals')).items;
    await navigate(page, 'chat');
    const input = page.getByTestId('chat-input');
    await input.fill(en ? 'A question about my reserve' : 'Una pregunta sobre mi reserva');
    await input.press('Shift+Enter');
    await page.keyboard.insertText(en ? 'With a second line' : 'Con una segunda línea');
    const draft = await input.innerText();
    expect(draft).toContain('\n');
    await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true });
    await expect(input).toHaveText(draft);
    await expect(page.getByTestId('chat-transcript').locator('[data-message-id]')).toHaveCount(0);
    await input.press('Enter');
    await expect(page.getByRole('alert')).toContainText(en ? 'Text interpretation is unavailable' : 'La interpretación de texto no está disponible');
    await expect(input).toHaveText(draft);
    const unavailable = (await read(page, '/chat/conversations')).items;
    for (const conversation of unavailable) {
      const persisted = await read(page, `/chat/conversations/${conversation.id}`);
      expect(persisted.messages.flatMap((message: { cards: {kind:string}[] }) => message.cards).some((card: {kind:string}) => ['proposal', 'receipt'].includes(card.kind))).toBe(false);
    }
    expect((await read(page, '/goals')).items).toEqual(goalsBefore);
    const conversationURL = page.url();
    await navigate(page, 'overview');
    await page.goBack();
    await expect(page).toHaveURL(conversationURL);
    await expect(page.getByTestId('chat-input')).toHaveText(draft);
    await screenshot(page, `${language}-390-keyless-draft`);
    await page.getByRole('button', { name: en ? 'Import a statement' : 'Importar un estado de cuenta', exact: true }).click();
    await expect(page).toHaveURL(/#transactions\?.*import=1/);
    await expect(page.getByRole('dialog', { name: en ? 'Import bank statement' : 'Importar estado de cuenta', exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(new URL(page.url().replace('#', '?')).searchParams.get('import')).not.toBe('1');
  });
}

test('a disconnected prepared turn retries its persisted proposal and confirms only once', async ({ page }) => {
  await enterGuest(page, 'en', 'demo');
  const baseline = (await read(page, '/goals')).items.length;
  await navigate(page, 'chat');
  const turnIds: string[] = [];
  await page.route('**/api/platform/chat/turn', async route => {
    turnIds.push(route.request().postDataJSON().turn_id);
    if (turnIds.length === 1) {
      const storedResponse = await route.fetch();
      expect(storedResponse.ok()).toBe(true);
      await storedResponse.body();
      await route.abort('connectionreset');
    } else await route.continue();
  });
  try {
    await page.locator('[data-example-id="sample-goal"]').click();
    await expect(page.getByRole('alert')).toBeVisible();
    expect((await read(page, '/chat/conversations')).items).toHaveLength(1);
    await page.getByRole('alert').getByRole('button', { name: 'Retry', exact: true }).click();
    await expect(page.locator('[data-proposal-status="pending"]')).toHaveCount(1);
    expect(turnIds).toHaveLength(2);
    expect(turnIds[1]).toBe(turnIds[0]);
    await page.locator('[data-proposal-status="pending"]').getByRole('button', { name: 'Confirm change', exact: true }).click();
    await expect(page.locator('[data-receipt-id]')).toHaveCount(1);
    expect((await read(page, '/goals')).items).toHaveLength(baseline + 1);
    await page.reload();
    await expect(page.locator('[data-receipt-id]')).toHaveCount(1);
    expect((await read(page, '/goals')).items).toHaveLength(baseline + 1);
  } finally { await page.unroute('**/api/platform/chat/turn'); }
});

test('staged chat text stays out of URLs and cannot cross user or reset generations', async ({ page }) => {
  await login(page);
  await navigate(page, 'overview');
  const privateText = 'Browser private savings question 742';
  await page.getByTestId('chat-input').fill(privateText);
  await page.getByTestId('chat-send').click();
  await expect(page).toHaveURL(/#chat\?draft=[a-z0-9-]+/);
  const stagedURL = page.url();
  expect(decodeURIComponent(stagedURL)).not.toContain(privateText);
  await expect(page.getByTestId('chat-input')).toHaveText(privateText);
  const edited = privateText + ' amended';
  await page.getByTestId('chat-input').fill(edited);
  await page.reload();
  await expect(page.getByTestId('chat-input')).toHaveText(edited);
  async function signOut() {
    await openProfile(page);
    await page.getByRole('dialog', { name: /^(Your workspace|Tu espacio)$/ }).getByRole('button', { name: /^(Sign out|Cerrar sesión)$/ }).click();
    await expect(page.getByRole('button', { name: /^(Sign in|Iniciar sesión)$/ })).toBeVisible();
  }
  await signOut();
  await login(page, 'en', 'user-other');
  await page.goto(stagedURL);
  await expect(page.getByTestId('chat-input')).toHaveText('');
  await expect(page.locator('body')).not.toContainText(privateText);
  await signOut();
  await login(page);
  const settings = await read(page, '/settings');
  await navigate(page, 'settings');
  await openSettingsPanel(page, 'data');
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Reset household data', exact: true }).click();
  await dialog.getByLabel('Confirm the name', { exact: false }).fill(settings.household.name);
  await dialog.getByLabel('Type RESET THIS HOUSEHOLD to confirm', { exact: true }).fill('RESET THIS HOUSEHOLD');
  await dialog.getByRole('button', { name: 'Empty this household', exact: true }).click();
  await expect.poll(async () => (await read(page, '/accounts')).total).toBe(0);
  await page.goto(stagedURL);
  await expect(page.getByTestId('chat-input')).toHaveText('');
  await expect(page.locator('body')).not.toContainText(privateText);
});

test('navigating away from a detached turn cannot redirect or replace the new page', async ({ page }) => {
  await enterGuest(page, 'en', 'demo');
  await navigate(page, 'chat');
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let stored!: () => void;
  const persisted = new Promise<void>(resolve => { stored = resolve; });
  let finished!: () => void;
  const deliveryEnded = new Promise<void>(resolve => { finished = resolve; });
  await page.route('**/api/platform/chat/turn', async route => {
    try {
      const response = await route.fetch();
      expect(response.ok()).toBe(true);
      await response.body();
      stored();
      await gate;
      await route.abort('connectionreset');
    } finally { finished(); }
  });
  try {
    await page.locator('[data-example-id="spending"]').click();
    await persisted;
    await navigate(page, 'overview');
    release();
    await deliveryEnded;
    await expect(page).toHaveURL(/#overview$/);
    await expect(page.getByTestId('conversation-page')).toHaveCount(0);
    const conversations = (await read(page, '/chat/conversations')).items;
    expect(conversations).toHaveLength(1);
    await page.reload();
    await page.getByTestId('recent-conversations').locator(`[data-conversation-id="${conversations[0].id}"]`).getByRole('button').first().click();
    await expect(page.locator('.argus-fact')).not.toHaveCount(0);
    await expect(page).toHaveURL(new RegExp(`conversation_id=${conversations[0].id}`));
  } finally { release(); await page.unroute('**/api/platform/chat/turn'); }
});
