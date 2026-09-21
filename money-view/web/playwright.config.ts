import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    actionTimeout: 10_000,
    baseURL: "http://127.0.0.1:5192",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "bunx vite --host 127.0.0.1 --port 5192",
    env: { CLARA_TEST_API_ORIGIN: "http://127.0.0.1:8022" },
    url: "http://127.0.0.1:5192",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
