import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, navigate, screenshot, evidenceDirectory } from './fixtures';
import { enterGuest } from './experience-helpers';

for (const language of ['en', 'es'] as const) {
  test(`${language}: chat draft keeps send and attachment inside all five viewport widths`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 900 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await enterGuest(page, language, 'demo');
    await navigate(page, 'chat');
    await page.locator('[data-example-id="spending"]').click();
    await expect(page.locator('.argus-fact')).not.toHaveCount(0);
    await page.getByTestId('chat-input').fill(language === 'en' ? 'Keep this private draft' : 'Conserva este borrador privado');
    for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    });
    const measurements = await page.evaluate(() => {
      const selectors = ['.p-main', '.argus-conversation', '.argus-transcript', '.argus-composer-dock', '.argus-composer', '.argus-composer-editor', '.argus-composer-send', '.argus-composer-attach'];
      return { innerHeight, innerWidth, visualViewportHeight: visualViewport?.height, scrollY, elements: Object.fromEntries(selectors.map(selector => {
        const element = document.querySelector(selector);
        const box = element?.getBoundingClientRect();
        return [selector, box ? { top: box.top, bottom: box.bottom, height: box.height, width: box.width } : null];
      })) };
    });
    writeFileSync(join(evidenceDirectory, `${language}-${width}-composer-geometry.json`), JSON.stringify(measurements, null, 2));
    await screenshot(page, `${language}-${width}-chat-settled`);
    expect(measurements.innerHeight).toBe(900);
    expect(measurements.visualViewportHeight).toBe(900);
    for (const selector of ['.argus-composer-send', '.argus-composer-attach']) {
      const box = measurements.elements[selector];
      expect(box).not.toBeNull();
      expect(box!.bottom, `${selector}: ${JSON.stringify(measurements)}`).toBeLessThanOrEqual(measurements.innerHeight);
      expect(box!.top).toBeGreaterThanOrEqual(0);
    }
    }
  });
}
