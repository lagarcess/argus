import path from "node:path";
import { defineConfig } from "@playwright/test";

const webRoot = path.resolve(__dirname, "..");
const port = 3197;
const suppliedOrigin = process.env.PLAYWRIGHT_BASE_URL;
const appOrigin = suppliedOrigin ?? `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: __dirname,
  testMatch: "ecosystem-preview.spec.ts",
  outputDir: path.join(webRoot, "temp/ecosystem-preview-playwright"),
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: appOrigin,
    browserName: "chromium",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
    timezoneId: "America/Santo_Domingo",
    locale: "en-US",
    contextOptions: { reducedMotion: "reduce" },
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: suppliedOrigin ? undefined : {
    command: `node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port ${port}`,
    cwd: webRoot,
    url: `${appOrigin}/dev/ecosystem`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
    env: {
      NEXT_DIST_DIR: ".next-ecosystem-preview",
      NEXT_PUBLIC_ENABLE_SPANISH: "true",
      NEXT_PUBLIC_ARGUS_API_URL: "http://127.0.0.1:3999/api/v1",
    },
  },
});
