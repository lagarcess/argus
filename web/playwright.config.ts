import { defineConfig, devices } from "@playwright/test";

const runId = `${Date.now()}-${process.pid}`;

export default defineConfig({
  testDir: "./e2e",
  outputDir: `./temp/playwright-results/${runId}`,
  lastRunFile: `./temp/playwright/${runId}.last-run.json`,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  retries: 0,
  workers: 2,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "node ./node_modules/next/dist/bin/next dev --port 3000",
    port: 3000,
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_MOCK_AUTH: "true",
      NEXT_PUBLIC_ENABLE_DEV_ONBOARDING_RESET: "true",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
