import { test, expect } from '@playwright/test';

test.describe('Landing Page Visual Regression', () => {
  test('should match baseline snapshot', async ({ page }) => {
    // Navigate to landing page
    await page.goto('/');

    // Wait for the main headline to be visible to ensure the page has loaded
    await expect(page.locator('h1')).toBeVisible();

    // Small delay to let smooth animations settle (like the glow effect)
    await page.waitForTimeout(2000);

    // Capture screenshot and compare
    await expect(page).toHaveScreenshot('landing-page.png', {
      fullPage: true,
    });
  });
});
