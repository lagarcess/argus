import { test, expect } from '@playwright/test';
import { existsSync } from 'node:fs';

test.describe('Landing Page Visual Regression', () => {
  test('should match baseline snapshot', async ({ page }, testInfo) => {
    // Navigate to landing page
    await page.goto('/');

    // Wait for the main headline to be visible to ensure the page has loaded
    await expect(page.locator('h1')).toBeVisible();

    // Small delay to let smooth animations settle (like the glow effect)
    await page.waitForTimeout(2000);

    const baselinePath = testInfo.snapshotPath('landing-page.png');
    test.skip(!existsSync(baselinePath), 'Landing baseline snapshot not generated yet. Run with --update-snapshots once.');

    // Capture screenshot and compare
    await expect(page).toHaveScreenshot('landing-page.png', {
      fullPage: true,
    });
  });
});
