import { defineConfig } from "@playwright/test";
import path from "node:path";
import base from "../playwright.config";

const port = Number(process.env.PLAYWRIGHT_PORT ?? 3190);
const apiPort = Number(process.env.REGISTRY_RECEIPT_API_PORT ?? 3191);
const cwd = path.resolve(__dirname, "..");

/** The public SSR route reads this fixture server; browser API calls are routed by the specs. */
export default defineConfig({
  ...base,
  testDir: ".",
  testMatch: ["tool-registry.spec.ts", "receipt-sharing-focus.spec.ts", "registry-receipts.spec.ts"],
  outputDir: `../temp/playwright-results/registry-receipts-${process.pid}`,
  use: { ...base.use, baseURL: `http://localhost:${port}` },
  webServer: [
    { command: "bun e2e/support/registry-receipt-server.ts", cwd, port: apiPort, reuseExistingServer: false },
    { command: `node ./node_modules/next/dist/bin/next dev --port ${port}`, cwd, port, reuseExistingServer: false, timeout: 120_000,
      env: {
        NEXT_PUBLIC_MOCK_AUTH: "true", NEXT_PUBLIC_ENABLE_SPANISH: "true",
        NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED: "true",
        NEXT_PUBLIC_ARGUS_API_URL: `http://127.0.0.1:${apiPort}/api/v1`,
      },
    },
  ],
});
