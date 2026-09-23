import type { Page } from '@playwright/test';
import { test, expect, read, screenshot, noOverflow, navigate, openSettingsPanel } from './fixtures';

import { enterGuest } from './experience-helpers';

for (const language of ['en', 'es'] as const) {
  test(`${language}: empty guest begins with unknown currency and no manufactured money`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const session = await enterGuest(page, language, 'empty');
    expect(session.currency_context).toMatchObject({ currency: null, source: 'unknown', account_id: null });
    expect((await read(page, '/accounts')).total).toBe(0);
    expect((await read(page, '/transactions?limit=25')).total).toBe(0);
    await expect(page.getByRole('combobox', { name: /Display currency, no conversion|Moneda, sin conversión/ })).toHaveValue('');
    await expect(page.getByRole('heading', { name: language === 'en' ? 'A clear place to begin' : 'Un lugar claro para empezar' })).toBeVisible();
    await expect(page.locator('.p-networth-main')).toHaveCount(0);
    await screenshot(page, `${language}-390-empty-guest`);
    await page.reload();
    await expect(page.locator('.p-main h1')).toBeVisible();
    const restored = await read(page, '/session');
    expect(restored.user.id).toBe(session.user.id);
    expect(restored.household.id).toBe(session.household.id);
    expect(restored.currency_context.currency).toBeNull();
    await noOverflow(page);
  });

  for (const width of [1440, 1024, 768, 390, 320]) {
    test(`${language} ${width}: guest money and Omnisearch keyboard selection preserve record identity`, async ({ page }) => {
      const errors: string[] = [];
      const external: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        const url = new URL(request.url());
        if (['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)) external.push(url.origin);
      });
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const session = await enterGuest(page, language, 'demo');
      expect(session.currency_context.currency).not.toBeNull();
      const accounts = await read(page, '/accounts');
      expect(accounts.total).toBeGreaterThan(0);
      await expect(page.locator('.p-networth-main')).toBeVisible();
      await screenshot(page, `${language}-${width}-money-home`);
      await noOverflow(page);

      await navigate(page, 'chat');
      await page.locator('[data-example-id="spending"]').click();
      await expect(page.locator('.argus-fact')).not.toHaveCount(0);
      const draft = language === 'en' ? 'Keep this private draft' : 'Conserva este borrador privado';
      await page.getByTestId('chat-input').fill(draft);
      expect(decodeURIComponent(page.url())).not.toContain(draft);
      await screenshot(page, `${language}-${width}-chat`);
      await noOverflow(page);
      const conversationURL = page.url();
      await navigate(page, 'settings');
      await screenshot(page, `${language}-${width}-settings`);
      await openSettingsPanel(page, 'privacy');
      await expect(page.getByRole('dialog')).toHaveCount(1);
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(page.getByRole('button', { name: language === 'en' ? 'Privacy' : 'Privacidad', exact: true })).toBeFocused();
      await page.goto(conversationURL);
      await expect(page.getByTestId('chat-input')).toHaveText(draft);
      await page.getByRole('button', { name: language === 'en' ? 'Import a statement' : 'Importar un estado de cuenta', exact: true }).click();
      await expect(page.getByRole('dialog', { name: language === 'en' ? 'Import bank statement' : 'Importar estado de cuenta', exact: true })).toBeVisible();
      await screenshot(page, `${language}-${width}-import`);
      await noOverflow(page);
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);

      const searchTrigger = page.getByRole('button', { name: language === 'en' ? 'Search workspace' : 'Buscar en el espacio', exact: true });
      const directSearch = await searchTrigger.isVisible();
      const trigger = directSearch ? searchTrigger : page.getByRole('button', { name: language === 'en' ? 'Open navigation' : 'Abrir navegación', exact: true });
      await trigger.click();
      if (!directSearch) await page.getByRole('dialog', { name: 'Argus', exact: true }).getByRole('button', { name: language === 'en' ? /^Search/ : /^Buscar/ }).click();
      const dialog = page.getByRole('dialog', { name: language === 'en' ? 'Search' : 'Buscar', exact: true });
      await expect(dialog).toBeVisible();
      const search = dialog.getByRole('combobox', { name: language === 'en' ? 'Search' : 'Buscar', exact: true });
      await expect(search).toBeFocused();
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      if (!directSearch) {
        const drawer = page.getByRole('dialog', { name: 'Argus', exact: true });
        await expect(drawer).toBeVisible();
        await expect(drawer.getByRole('button', { name: language === 'en' ? /^Search/ : /^Buscar/ })).toBeFocused();
        await page.keyboard.press('Escape');
        await expect(drawer).toHaveCount(0);
      }
      await expect(trigger).toBeFocused();

      await page.keyboard.press('ControlOrMeta+k');
      await expect(search).toBeFocused();
      await dialog.getByRole('combobox', { name: language === 'en' ? 'Search in' : 'Buscar en', exact: true }).selectOption('account');
      await expect(dialog.getByRole('listbox')).toHaveAttribute('aria-busy', 'false');
      const options = dialog.getByRole('listbox').getByRole('option');
      await expect.poll(() => options.count()).toBeGreaterThan(1);
      const first = await options.nth(0).getAttribute('id');
      await expect(search).toHaveAttribute('aria-activedescendant', first!);
      await search.press('ArrowDown');
      await expect(options.nth(1)).toHaveAttribute('aria-selected', 'true');
      await search.press('ArrowUp');
      await expect(options.nth(0)).toHaveAttribute('aria-selected', 'true');

      const account = accounts.items[0];
      const response = page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.pathname === '/api/platform/search' && url.searchParams.get('q') === account.name;
      });
      await search.fill(account.name);
      const matched = await response;
      expect(matched.ok()).toBe(true);
      const payload = await matched.json();
      expect(payload.items.length).toBeLessThanOrEqual(20);
      expect(JSON.stringify(payload).length).toBeLessThan(100_000);
      expect(payload.items.some((item: { target: { record_id: string } }) => item.target.record_id === account.id)).toBe(true);
      await expect(dialog.getByRole('listbox')).toHaveAttribute('aria-busy', 'false');
      await expect(options.first()).toContainText(account.name);
      await screenshot(page, `${language}-${width}-search`);
      await noOverflow(page);
      await search.press('Enter');
      if (width < 1024) {
        await expect(dialog.getByRole('button', { name: language === 'en' ? 'Back to results' : 'Volver a resultados', exact: true })).toBeFocused();
        await screenshot(page, `${language}-${width}-search-preview`);
        await page.keyboard.press('Escape');
        await expect(search).toBeFocused();
        await search.press('Enter');
        await dialog.getByRole('button', { name: language === 'en' ? 'Open record' : 'Abrir registro', exact: true }).click();
      }
      await expect(dialog).toHaveCount(0);
      await expect(page).toHaveURL(new RegExp(`#accounts\\?.*record_id=${account.id}`));
      await expect(page.locator('.p-main')).toContainText(account.name);
      await noOverflow(page);
      expect(errors).toEqual([]);
      expect(external).toEqual([]);
    });
  }
}
