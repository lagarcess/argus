import path from "node:path";
import base from "./breakpoint-baselines.playwright.config";

const config = {
  ...base,
  testMatch: ["menu-settings-width.spec.ts", "menu-settings-phone-audit.spec.ts"],
  outputDir: path.resolve(__dirname, "../../temp/menu-settings-width"),
  snapshotDir: path.resolve(
    __dirname,
    "../../docs/reports/evidence/menu-settings-width-contract",
  ),
  // Keep these captures beside the audit, with the inherited 100-pixel budget.
  timeout: 120_000,
  use: { ...base.use, screenshot: "only-on-failure" as const },
};

export default config;
