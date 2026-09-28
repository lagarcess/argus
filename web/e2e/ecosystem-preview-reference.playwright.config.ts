import path from "node:path";
import { defineConfig } from "@playwright/test";

// Server lifecycles belong to the release captain. This observational harness
// never starts, replaces, builds, or stops any of the three reference servers.
export default defineConfig({
  testDir: __dirname,
  testMatch: "ecosystem-preview-reference.gate.ts",
  outputDir: path.resolve(__dirname, "../temp/ecosystem-preview-reference-results"),
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    browserName: "chromium",
    headless: true,
    deviceScaleFactor: 1,
    timezoneId: "America/Santo_Domingo",
    locale: "en-US",
    colorScheme: "light",
    contextOptions: { reducedMotion: "reduce" },
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
});
