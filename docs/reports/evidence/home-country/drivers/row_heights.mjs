// Review evidence for PR #593 (Codex round 1, the 44px finding): how tall the
// Preferences rows render where a finger reaches them (390 px, touch, drawer)
// and where a pointer does (1280 px, rail popover). The account is mocked, so
// no API is needed; the web dev server runs on HC_WEB_PORT.
// Usage: HC_TREE=<tree> node row_heights.mjs
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const TREE = process.env.HC_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/home-country/review`;
mkdirSync(OUT, { recursive: true });
const WEB = `http://localhost:${process.env.HC_WEB_PORT || "3000"}`;
const copy = JSON.parse(readFileSync(`${TREE}/web/public/locales/en/common.json`, "utf-8"));
const profile = {
  id: "rows",
  email: "rows@example.com",
  username: "rows",
  display_name: "Rows",
  language: "en",
  locale: "en-US",
  avatar_theme: "ocean",
  country: null,
  currency_override: null,
  currency: null,
};

async function activate(page, locator) {
  await locator.focus();
  await page.keyboard.press("Enter");
}

const json = (body) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

const browser = await chromium.launch();
const report = [];
for (const layout of [
  { name: "phone-390", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
  { name: "desktop-1280", viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false },
]) {
  const context = await browser.newContext({
    viewport: layout.viewport,
    isMobile: layout.isMobile,
    hasTouch: layout.hasTouch,
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  await page.route("**/api/v1/me", (route) => route.fulfill(json({ user: profile, account_kind: "registered" })));
  await page.route("**/api/v1/conversations", (route) => route.fulfill(json({ items: [], next_cursor: null })));
  await page.goto(`${WEB}/chat`, { waitUntil: "networkidle" });
  if (layout.isMobile) {
    await activate(page, page.getByRole("button", { name: copy.sidebar?.open ?? "Open sidebar" }));
  }
  await activate(page, page.getByRole("button", { name: copy.common.settings }));
  await activate(page, page.getByRole("button", { name: copy.settings.preferences.title }));
  const rows = {};
  for (const [key, label] of [
    ["appearance", copy.settings.app.appearance],
    ["language", copy.settings.app.language],
    ["country", copy.settings.app.home_country],
  ]) {
    const button = page.getByRole("button", { name: label, exact: true });
    await button.waitFor();
    rows[key] = await button.evaluate((node) => ({
      height: node.getBoundingClientRect().height,
      minHeight: getComputedStyle(node).minHeight,
    }));
  }
  report.push({ layout: layout.name, rows });
  await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
  await page.screenshot({ path: `${OUT}/preferences-rows-${layout.name}.png` });
  await context.close();
}
await browser.close();
writeFileSync(`${OUT}/row-heights.json`, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
