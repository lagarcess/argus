import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "guest-auth-captcha-ux.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:3011",
    headless: true,
    viewport: { width: 1422, height: 800 },
  },
});
