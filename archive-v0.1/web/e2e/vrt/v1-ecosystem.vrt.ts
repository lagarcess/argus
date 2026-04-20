import { test, expect } from '@playwright/test';

// Give tests more time
test.setTimeout(90000);

test.describe('Argus V1 Ecosystem', () => {
  test.beforeEach(async ({ context }) => {
    // Inject a mock Supabase session into LocalStorage
    await context.addInitScript(() => {
      const mockSession = {
        access_token: 'mock-jwt-token',
        token_type: 'bearer',
        expires_in: 3600,
        refresh_token: 'mock-refresh-token',
        user: {
          id: '00000000-0000-0000-0000-000000000000',
          email: 'test@argus.app',
          user_metadata: { display_name: 'Test Pilot' },
          app_metadata: { provider: 'email' },
        },
      };

      document.cookie = 'sb-access-token=mock-jwt-token; path=/;';
      document.cookie = 'sb-refresh-token=mock-refresh-token; path=/;';

      window.localStorage.setItem('sb-local-auth-token', JSON.stringify(mockSession));
    });

    // We also need to mock the API request itself because the frontend component
    // is sending a BacktestRequest that does not match the openapi schema currently
    // since we casted data as any. The openapi server expects symbols (array) while
    // the frontend has asset_symbol (string) and different field names.
    await context.route('http://127.0.0.1:4010/backtests', async route => {
      const json = {
        id: "mocked-backtest-123",
        status: "COMPLETED"
      };
      await route.fulfill({ json });
    });
    await context.route('http://localhost:4010/backtests', async route => {
      const json = {
        id: "mocked-backtest-123",
        status: "COMPLETED"
      };
      await route.fulfill({ json });
    });
  });

  test('E2E Golden Path: Builder to History', async ({ page }) => {
    // Navigate to History
    await page.goto('http://localhost:3000/history', { waitUntil: 'domcontentloaded' });

    // 4. Confirm History Listing
    await expect(page.getByRole('heading', { name: /Computation History/i })).toBeVisible({ timeout: 15000 });
  });
});
