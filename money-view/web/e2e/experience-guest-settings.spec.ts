import { test, expect, navigate, openSettingsPanel, read, screenshot, noOverflow } from './fixtures';
import { enterGuest } from './experience-helpers';

for (const language of ['en', 'es'] as const) {
  test(`${language}: guest settings become password settings only after claim`, async ({ page }) => {
    const en = language === 'en';
    await page.setViewportSize({ width: 390, height: 844 });
    await enterGuest(page, language, 'empty');
    await navigate(page, 'settings');
    await openSettingsPanel(page, 'security');
    const dialog = page.getByRole('dialog');
    await expect(dialog.locator('input[type="password"]')).toHaveCount(0);
    await expect(dialog).toContainText(en ? 'This guest workspace has no password.' : 'Este espacio de invitado no tiene contraseña.');
    await dialog.getByRole('button', { name: en ? 'End all sessions' : 'Cerrar todas las sesiones', exact: true }).click();
    await expect(dialog.locator('.settings-confirm')).toContainText(en ? 'may lose access' : 'puede hacerte perder el acceso');
    await screenshot(page, `${language}-390-guest-security`);
    await noOverflow(page);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await openSettingsPanel(page, 'data');
    const deleteName = en ? 'Delete my local account' : 'Eliminar mi cuenta local';
    await expect(dialog.getByRole('button', { name: deleteName, exact: true })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: en ? 'Reset household data' : 'Restablecer datos del hogar', exact: true })).toBeEnabled();
    await screenshot(page, `${language}-390-guest-data`);
    await noOverflow(page);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await page.getByRole('button', { name: en ? 'Keep workspace' : 'Conservar espacio', exact: true }).click();
    await dialog.getByLabel(en ? 'Your name' : 'Tu nombre', { exact: true }).fill('Settings owner');
    await dialog.getByLabel(en ? 'Password' : 'Contraseña', { exact: false }).fill('Guest-settings-2026!');
    await dialog.getByRole('button', { name: en ? 'Keep workspace' : 'Conservar espacio', exact: true }).click();
    await dialog.getByRole('button', { name: en ? 'Continue' : 'Continuar', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect((await read(page, '/settings')).capabilities.local_passwords).toBe(true);
    await navigate(page, 'settings');
    await openSettingsPanel(page, 'security');
    await expect(dialog.getByLabel(en ? 'Current password' : 'Contraseña actual', { exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await openSettingsPanel(page, 'data');
    await expect(dialog.getByRole('button', { name: deleteName, exact: true })).toBeVisible();
  });
}
