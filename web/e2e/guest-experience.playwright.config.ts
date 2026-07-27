import path from "node:path";
import { defineConfig, devices } from "@playwright/test";
import { guestQaEndpointConfig } from "./support/guest-qa-endpoints";

const repositoryRoot = path.resolve(__dirname, "../..");
const preflight = process.env.ARGUS_GUEST_QA_PREFLIGHT === "true";
const entry = process.env.ARGUS_GUEST_QA_ENTRY === "true";
const runId = `${Date.now()}-${process.pid}`;
const { appOrigin, appPort } = guestQaEndpointConfig();

export default defineConfig({
  testDir: path.join(repositoryRoot, "web/e2e"),
  testMatch: preflight
    ? "guest-experience.preflight.spec.ts"
    : entry
      ? "guest-entry.spec.ts"
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
    baseURL: appOrigin,
    headless: false,
    trace: "off",
    video: "off",
    screenshot: "off",
    serviceWorkers: "block",
  },
  webServer: {
    command: `bun run start --hostname 127.0.0.1 --port ${appPort}`,
    cwd: path.join(repositoryRoot, "web"),
    url: appOrigin,
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
