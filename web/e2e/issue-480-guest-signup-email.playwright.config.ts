import path from "node:path";
import { defineConfig, devices } from "@playwright/test";
import { guestQaEndpointConfig } from "./support/guest-qa-endpoints";

const repositoryRoot = path.resolve(__dirname, "../..");
const { appOrigin, appPort } = guestQaEndpointConfig();

export default defineConfig({
  testDir: path.join(repositoryRoot, "web/e2e"),
  testMatch: "issue-480-guest-signup-email.spec.ts",
  outputDir: path.join(
    repositoryRoot,
    "temp/issue-480-guest-signup-email-playwright",
  ),
  timeout: 300_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: appOrigin,
    headless: true,
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
