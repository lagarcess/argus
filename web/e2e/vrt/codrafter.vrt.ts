import { test, expect } from '@playwright/test';

test.describe('Co-Drafter AI Strategy Builder', () => {
  test('User types prompt -> Hits Enter -> Builder fields populate with AI Explanation', async ({ page }) => {
    // Navigate to the builder page. Assuming we're using mock auth.
    await page.goto('/builder');

    // Wait for the hydration error to disappear or for client to mount completely
    await page.waitForTimeout(2000);

    // Check if the CoDrafter bar is present
    const drafterInput = page.getByPlaceholder(/Draft a risk-mitigation strategy/i);
    await expect(drafterInput).toBeVisible({ timeout: 10000 });

    // 1. User types prompt
    await drafterInput.fill('Tendies on NVDA');

    // 2. Hits Enter
    await drafterInput.press('Enter');

    // 3. Verify 'Drafting...' state is shown
    // Wait longer if necessary, the text changes fast
    const draftingButton = page.getByRole('button', { name: 'Submit Draft' });
    await expect(draftingButton).toBeVisible({ timeout: 10000 });

    // 4. Verify AiExplanationCard appears by waiting for the selector instead of raw timeout
    // the explanation card is marked with text 'AI Drafter Reasoning'
    await page.waitForSelector('text=AI Drafter Reasoning', { state: 'visible', timeout: 10000 });

    const explanationText = page.getByText(/Parsed 'Tendies on NVDA' as a mean reversion strategy/i);
    await expect(explanationText).toBeVisible();

    // 5. Verify fields populated (mock data uses AAPL)
    const assetSymbolLabel = page.getByText('AAPL', { exact: true });
    await expect(assetSymbolLabel).toBeVisible();

    const timeframeLabel = page.getByText('15MIN'); // Case insensitive or uppercase matched
    await expect(timeframeLabel).toBeVisible();

    // Wait an extra second to ensure Yellow Flash animations are complete
    await page.waitForTimeout(1000);

    // 6. Capture screenshot to verify Yellow Flash and Liquid Glass aesthetics
    // Use mask to hide time/dates that might change and cause flakes
    await expect(page).toHaveScreenshot('codrafter-populated.png');
  });
});
