import { defineConfig, devices } from "@playwright/test";
const root = "/private/tmp/registry-declaration-browser-b17d2577";
export default defineConfig({
  testDir: `${root}/checkout/web/e2e`,
  testMatch: ["tool-registry.spec.ts", "registry-signal-control.spec.ts"],
  outputDir: `${root}/test-results`,
  timeout: 90_000, expect: { timeout: 10_000 }, workers: 1, retries: 0,
  reporter: [["list"], ["json", { outputFile: `${root}/playwright-results.json` }]],
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:3195", viewport: { width: 1280, height: 1000 }, serviceWorkers: "block", trace: "retain-on-failure" },
  webServer: {
    command: "node ./node_modules/next/dist/bin/next dev --webpack --hostname 127.0.0.1 --port 3195",
    cwd: `${root}/checkout/web`, url: "http://127.0.0.1:3195", reuseExistingServer: false, timeout: 120_000,
    env: { NEXT_TELEMETRY_DISABLED: "1", NEXT_PUBLIC_MOCK_AUTH: "true", NEXT_PUBLIC_ENABLE_SPANISH: "true", NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED: "false", NEXT_PUBLIC_ARGUS_API_URL: "http://127.0.0.1:8318/api/v1" },
  },
});
