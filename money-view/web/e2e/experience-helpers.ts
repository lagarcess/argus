import type { Page } from '@playwright/test';
import { expect, read, screenshot } from './fixtures';

export type Language = 'en' | 'es';

export async function enterGuest(page: Page, language: Language, mode: 'demo' | 'empty') {
  await page.goto('/');
  if (language === 'en') await page.getByRole('button', { name: 'English', exact: true }).click();
  await expect(page).toHaveTitle(/Argus/);
  await expect(page.getByTestId('chat-input')).toBeVisible();
  await expect(page.getByTestId('chat-send')).toBeDisabled();
  await screenshot(page, `${language}-${page.viewportSize()!.width}-guest`);
  const name = mode === 'demo'
    ? (language === 'en' ? 'Explore the demo' : 'Explorar la demo')
    : (language === 'en' ? 'Start with my own records' : 'Empezar con mis registros');
  await page.getByRole('button', { name, exact: true }).click();
  await expect(page.locator('.platform-shell')).toHaveAttribute('data-page', 'overview');
  await expect(page.locator('.p-main h1')).toBeVisible();
  const session = await read(page, '/session');
  expect(session.guest.is_guest).toBe(true);
  expect(session.guest.mode).toBe(mode);
  return session;
}
