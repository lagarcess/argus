import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Visual baselines for the surfaces no queued lane is rewriting.
 *
 * A visual suite is only worth having if red means "something changed".
 * Everything here exists to remove a reason for a false red:
 *
 *  - fixture data, so no model output or live market data reaches a capture;
 *  - a fixed timezone and locale, because the allowance panel renders dates and
 *    a machine in another zone would otherwise fail every run;
 *  - `deviceScaleFactor: 1` and `scale: "css"`, so a retina laptop and a CI
 *    container rasterise at the same size;
 *  - animations disabled and the caret hidden, so a capture taken half a second
 *    later is the same bytes;
 *  - a per-pixel `threshold` plus a small `maxDiffPixelRatio`, which absorbs
 *    font antialiasing without absorbing a moved element.
 *
 * Baselines are platform-suffixed. CI is ubuntu, so the committed set is the
 * linux one, generated in the Playwright image that matches the pinned version:
 *
 *   docker run --rm -v "$PWD":/w -w /w/web mcr.microsoft.com/playwright:v1.59.1-noble \
 *     npx playwright test -c e2e/breakpoint-baselines.playwright.config.ts --update-snapshots
 *
 * Run locally the same way to refresh them; a darwin run writes its own set and
 * leaves the committed linux baselines alone.
 */

const repositoryRoot = path.resolve(__dirname, "../..");
const port = Number(process.env.ARGUS_BREAKPOINT_BASELINE_PORT ?? 3195);
/* Set when the browser runs in the linux container and the dev server runs on
   the host, which is how the committed linux baselines are produced. */
const externalBaseURL = process.env.PLAYWRIGHT_BASE_URL;
const appOrigin = externalBaseURL ?? `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: path.join(repositoryRoot, "web/e2e"),
  testMatch: "breakpoint-baselines.spec.ts",
  outputDir: path.join(repositoryRoot, "temp/breakpoint-baselines-playwright"),
  snapshotDir: path.join(repositoryRoot, "web/e2e/__screenshots__"),
  snapshotPathTemplate:
    "{snapshotDir}/{platform}/{arg}{ext}",
  timeout: 90_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      // Absorbs antialiasing, not layout: a shifted element moves far more
      // than 1% of the pixels in a panel-sized capture.
      threshold: 0.2,
      maxDiffPixelRatio: 0.01,
    },
  },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: appOrigin,
    trace: "off",
    video: "off",
    timezoneId: "UTC",
    locale: "en-US",
    deviceScaleFactor: 1,
  },
  webServer: externalBaseURL ? undefined : {
    command: `node ./node_modules/next/dist/bin/next dev --port ${port}`,
    cwd: path.join(repositoryRoot, "web"),
    url: appOrigin,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: "ignore",
    stderr: "pipe",
    env: {
      NEXT_PUBLIC_MOCK_AUTH: "true",
      NEXT_PUBLIC_ENABLE_SPANISH: "true",
      NEXT_PUBLIC_GUEST_ACCESS_ENABLED: "true",
      NEXT_PUBLIC_ARGUS_API_URL: "http://127.0.0.1:3999/api/v1",
      NEXT_PUBLIC_SUPABASE_URL: "https://test-project.supabase.co",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "test-anon-key",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
