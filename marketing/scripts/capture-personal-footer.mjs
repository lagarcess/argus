import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile, rename } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const baseURL = process.env.MARKETING_CAPTURE_URL ?? 'http://127.0.0.1:4512';
const root = new URL('../../', import.meta.url);
const output = new URL('docs/reports/evidence/cuadrao-marketing-touchup/personal-footer/screens/', root);
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const captures = [];
const errors = [];
try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    for (const [route, locale] of [['/personal', 'es'], ['/en/personal', 'en']]) {
      const record = viewport.width === 1440 && locale === 'es';
      const context = await browser.newContext({ viewport, reducedMotion: 'no-preference', ...(record ? { recordVideo: { dir: fileURLToPath(output), size: viewport } } : {}) });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(new URL(route, baseURL).href);
      await expect(page.locator('#personal-email')).toBeEnabled();
      await page.evaluate(() => document.fonts.ready);
      const frame = page.locator('[data-footer-peek]');
      await expect.poll(() => frame.locator('img').evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))).toBe(true);
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForTimeout(800);
      const shot = async state => {
        const file = `footer-${locale}-${viewport.width}-${state}.png`;
        await page.screenshot({ path: fileURLToPath(new URL(file, output)) });
        captures.push({ file, route, ...viewport, state });
      };
      await shot('rest');
      await frame.evaluate(target => {
        const touch = clientY => new Touch({ identifier: 1, target, clientX: 100, clientY });
        target.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, touches: [touch(700)] }));
        target.dispatchEvent(new TouchEvent('touchmove', { bubbles: true, touches: [touch(200)] }));
      });
      await page.waitForTimeout(65);
      await shot('first');
      await page.waitForTimeout(400);
      await shot('second');
      await page.waitForTimeout(500);
      await frame.dispatchEvent('touchend', { touches: [] });
      await page.waitForTimeout(800);
      await shot('settled');
      if (record) {
        await page.mouse.move(100, 800);
        await page.mouse.wheel(0, 400);
        await page.waitForTimeout(1100);
      }
      const video = record ? page.video() : null;
      await context.close();
      if (video) await rename(await video.path(), new URL('personal-footer-demo.webm', output));
    }
  }
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(new URL('/', baseURL).href);
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: fileURLToPath(new URL('business-footer-unchanged.png', output)) });
} finally { await browser.close(); }
if (errors.length) throw new Error(JSON.stringify(errors));
await writeFile(new URL('manifest.json', output), JSON.stringify({ sourceCommit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: fileURLToPath(root), encoding: 'utf8' }).trim(), capturedAt: new Date().toISOString(), baseURL, browser: 'Playwright Chromium desktop and narrow viewport; dispatched touch plus native wheel', forms: 'No submissions or provider requests', captures }, null, 2) + '\n');
console.log(fileURLToPath(output));
