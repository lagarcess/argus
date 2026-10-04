import path from "node:path";
import { defineConfig } from "@playwright/test";

// The parent builds and starts the isolated production output. Keeping that
// lifecycle separate avoids deleting or replacing another lane's Next output.
export default defineConfig({
  testDir: __dirname,
  testMatch: "ecosystem-preview-production.gate.ts",
  outputDir: path.resolve(__dirname, "../temp/ecosystem-preview-production"),
  timeout: 30_000,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3198",
  },
});
