import path from "node:path";
import base from "./breakpoint-baselines.playwright.config";

const config = {
  ...base,
  testMatch: ["drawer-overlay-motion.spec.ts", "menu-settings-phone-audit.spec.ts", "menu-settings-surfaces.spec.ts", "menu-settings-auth-regression.spec.ts"],
  outputDir: path.resolve(__dirname, "../../temp/menu-settings-contract-audit"),
  // Observational screenshots use page.screenshot in audit/. This runner never
  // generates or updates the existing breakpoint screenshot baselines.
  timeout: 30_000,
  use: { ...base.use, screenshot: "only-on-failure" as const },
};

export default config;
