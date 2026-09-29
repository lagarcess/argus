import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const repositoryRoot = path.resolve(__dirname, "../..");
const capture = process.env.ARGUS_ACCOUNTS_CAPTURE === "1";
const phase = process.env.ARGUS_ACCOUNTS_PHASE;
if (phase && !["flag-off", "restart-prepare", "restart-verify"].includes(phase)) {
  throw new Error("Unknown local financial accounts acceptance phase.");
}

export default defineConfig({
  testDir: __dirname,
  testMatch: /financial-accounts\.(journey|concurrency|gates)\.spec\.ts/,
  grep: phase ? new RegExp(`@${phase}\\b`) : /@(smoke|journey|concurrency|gates|responsive)\b/,
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  outputDir: path.join(repositoryRoot, "temp/web-financial-accounts-local/playwright"),
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:3198",
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    video: "off",
    screenshot: "off",
    serviceWorkers: "block",
  },
  // Durable capture owns its listener. Ordinary smoke uses the captain's
  // existing isolated listener and can never emit evidence unless capture is on.
  webServer: capture ? {
    command: "python3 ../scripts/qa/web-financial-accounts-local.py web",
    cwd: path.join(repositoryRoot, "web"),
    url: "http://127.0.0.1:3198/dev/financial-accounts",
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "ignore",
  } : undefined,
});
