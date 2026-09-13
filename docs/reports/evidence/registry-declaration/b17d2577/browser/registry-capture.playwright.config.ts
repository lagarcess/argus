import { defineConfig } from "@playwright/test";
import base from "./registry.playwright.config";
export default defineConfig({
  ...base,
  reporter: [["list"], ["json", { outputFile: "/private/tmp/registry-declaration-browser-b17d2577/capture-results.json" }]],
});
