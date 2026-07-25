import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const repositoryRoot = path.resolve(__dirname, "../..");
const preflight = process.env.ARGUS_GUEST_QA_PREFLIGHT === "true";
const runId = `${Date.now()}-${process.pid}`;

export default defineConfig({
  testDir: path.join(repositoryRoot, "web/e2e"),
  testMatch: preflight
    ? "guest-experience.preflight.spec.ts"
    : "guest-experience.spec.ts",
  globalSetup: path.join(
    repositoryRoot,
    "web/e2e/guest-experience.global-setup.ts",
  ),
  outputDir: path.join(
    repositoryRoot,
    "temp/qa-evidence-guest/playwright-private",
    runId,
  ),
  timeout: preflight ? 120_000 : 1_800_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: true,
  maxFailures: 1,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    headless: false,
    trace: "off",
    video: "off",
    screenshot: "off",
    serviceWorkers: "block",
  },
  webServer: {
    command: "bun run dev --hostname 127.0.0.1 --port 3000",
    cwd: path.join(repositoryRoot, "web"),
    url: "http://localhost:3000",
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "ignore",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
  ],
});
