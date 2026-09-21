import { test as base, expect, type Page } from '@playwright/test';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const appDirectory = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const evidenceDirectory = resolve(process.env.CLARA_EVIDENCE_DIR ?? join(appDirectory, 'docs/evidence/platform'));
const localPython = join(appDirectory, '.venv/bin/python');
const parentPython = resolve(appDirectory, '../.venv/bin/python');
const python = process.env.CLARA_TEST_PYTHON ?? (existsSync(localPython) ? localPython : existsSync(parentPython) ? parentPython : 'python3');
export const test = base.extend<{ backend: void }>({
  backend: [async ({ request }, use, testInfo) => {
    const directory = mkdtempSync(join(tmpdir(), 'clara-platform-browser-'));
    let output = '';
    const backend = spawn(python, ['-m', 'uvicorn', 'server.app:app', '--host', '127.0.0.1', '--port', '8022'], {
      cwd: appDirectory,
      env: { ...process.env, CLARA_DATABASE_PATH: join(directory, 'browser.sqlite3'), CLARA_LLM_API_KEY: '', CLARA_LLM_BASE_URL: '', CLARA_LLM_MODEL: '' },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    backend.stdout?.on('data', (chunk: Buffer) => { output += chunk.toString(); });
    backend.stderr?.on('data', (chunk: Buffer) => { output += chunk.toString(); });
    try {
      await expect.poll(async () => {
        if (backend.exitCode !== null) throw new Error(output);
        try { return (await request.get('http://127.0.0.1:8022/api/platform/demo/personas')).status(); } catch { return 0; }
      }, { timeout: 30_000 }).toBe(200);
      mkdirSync(evidenceDirectory, { recursive: true });
      await use();
    } finally {
      if (testInfo.status !== testInfo.expectedStatus) await testInfo.attach('backend-log', { body: output, contentType: 'text/plain' });
      if (backend.exitCode === null && backend.signalCode === null) {
        const stopped = new Promise<void>(done => backend.once('exit', () => done()));
        const force = setTimeout(() => backend.kill('SIGKILL'), 3000);
        backend.kill('SIGTERM'); await stopped; clearTimeout(force);
      }
      rmSync(directory, { recursive: true, force: true });
    }
  }, { auto: true }],
});
export { expect };
export async function navigate(page: Page, route: string) {
  await expect(page.locator('.p-topbar')).toBeVisible();
  const [name] = route.split('?');
  const desktop = page.locator(`.p-sidebar nav a[href="#${name}"]`);
  if (await desktop.isVisible()) await desktop.click();
  else if (['membership', 'employer', 'household'].includes(name) && await page.locator('.p-sidebar').isVisible()) {
    await page.locator('.p-household-button').click();
    const names: Record<string, RegExp> = { membership: /^(Membership|Membresía)$/, employer: /^(Employer benefits|Beneficios de empresa)$/, household: /^(Household|Hogar)$/ };
    await page.getByRole('dialog').getByRole('button', { name: names[name] }).click();
  } else {
    await page.getByRole('button', { name: /^(Open navigation|Abrir navegación)$/ }).click();
    await page.getByRole('dialog').locator(`a[href="#${name}"]`).click();
  }
  await expect(page).toHaveURL(new RegExp(`#${name}`));
  await expect(page.locator('.p-main h1')).toBeVisible();
}
export async function login(page: Page, locale: 'en' | 'es' = 'en', user = 'user-demo', currency = 'USD') {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Perfil local', exact: true }).selectOption(user);
  await page.getByLabel('Contraseña de demo', { exact: false }).fill('Clara-demo-2026!');
  await page.getByRole('button', { name: 'Abrir espacio' }).click();
  await expect(page.locator('.p-main h1')).toBeVisible();
  if (locale === 'en') {
    await navigate(page, 'settings');
    await page.getByRole('button', { name: /Idioma Español/ }).click();
    await page.getByRole('radio', { name: 'English' }).check();
    await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  }
  if (currency !== 'default') await page.getByRole('combobox', { name: /Display currency, no conversion|Moneda, sin conversión/ }).selectOption(currency);
}
export async function read(page: Page, path: string) {
  const response = await page.request.get(`/api/platform${path}`);
  expect(response.ok(), `${path}: ${response.status()}`).toBeTruthy();
  return response.json();
}
export async function screenshot(page: Page, name: string) {
  const dialog = page.getByRole('dialog');
  const hasDialog = await dialog.count() > 0;
  if (hasDialog) await dialog.evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: join(evidenceDirectory, `${name}.png`), fullPage: !hasDialog, animations: 'disabled' });
}
export async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
}
