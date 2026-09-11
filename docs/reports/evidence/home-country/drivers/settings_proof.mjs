// Browser proof for home country per user: Settings in English and Spanish
// against the real local API (memory persistence, mock auth, no provider keys).
// A pick saves through PATCH /me and the currency shown is the API's own
// derivation; the choice survives a reload; a save the API refuses (422 for a
// region that is not a country) is shown and put back. Every step records what
// GET /me holds at that moment.
// Usage: HC_TREE=<tree> node settings_proof.mjs   (web on 3000, API on 8000)
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const TREE = process.env.HC_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/home-country/browser`;
mkdirSync(OUT, { recursive: true });
const API = `http://127.0.0.1:${process.env.HC_API_PORT || "8000"}/api/v1`;
const WEB = `http://localhost:${process.env.HC_WEB_PORT || "3000"}`;
const COPY = Object.fromEntries(
  ["en", "es-419"].map((language) => [
    language,
    JSON.parse(readFileSync(`${TREE}/web/public/locales/${language}/common.json`, "utf-8")),
  ]),
);

async function patchMe(body) {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status} ${await response.text()}`);
  return (await response.json()).user;
}

async function account() {
  const { user } = await (await fetch(`${API}/me`)).json();
  return { country: user.country, currency_override: user.currency_override, currency: user.currency };
}

/** The dev overlay sits over the sidebar's corner, so controls are pressed, not clicked. */
async function activate(page, locator) {
  await locator.focus();
  await page.keyboard.press("Enter");
}

async function openPanel(page, copy) {
  await activate(page, page.getByRole("button", { name: copy.common.settings }));
  await activate(page, page.getByRole("button", { name: copy.settings.preferences.title }));
  await activate(page, page.getByRole("button", { name: copy.settings.app.home_country }));
  const panel = page.getByRole("dialog", { name: copy.settings.app.home_country });
  await panel.waitFor();
  return panel;
}

const segment = (panel, label) => panel.locator("button[aria-pressed]").filter({ hasText: label });
const startsWith = (label) => new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i");

async function shows(locator, text) {
  await locator.filter({ hasText: text }).first().waitFor({ timeout: 15_000 });
}

async function shot(page, name) {
  await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
  await page.screenshot({ path: `${OUT}/${name}.png` });
}

const browser = await chromium.launch();
const report = { web: WEB, api: API, steps: [] };
for (const language of ["en", "es-419"]) {
  const copy = COPY[language];
  const region = (code) => new Intl.DisplayNames([language], { type: "region" }).of(code);
  const currency = (code) => new Intl.DisplayNames([language], { type: "currency" }).of(code);
  const record = async (step, extra = {}) =>
    report.steps.push({ language, step, ...extra, account: await account() });

  await patchMe({
    language,
    locale: language === "es-419" ? "es-419" : "en-US",
    country: null,
    currency_override: null,
  });
  // The browser's own tag names a country, which the picker may suggest but never saves.
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 2,
    locale: language === "es-419" ? "es-MX" : "en-US",
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));

  await page.goto(`${WEB}/chat`, { waitUntil: "networkidle" });
  let panel = await openPanel(page, copy);
  await record("panel opened with a browser suggestion; nothing saved");
  await shot(page, `${language}-1-opened-with-suggestion`);

  await panel.getByRole("textbox").fill(region("MX"));
  await activate(page, panel.getByRole("button", { name: startsWith(region("MX")) }));
  await shows(segment(panel, copy.settings.app.currency), "MXN");
  await record("picked Mexico; the API derived MXN");
  await shot(page, `${language}-2-mexico-implies-mxn`);

  await activate(page, segment(panel, copy.settings.app.currency));
  await panel.getByRole("textbox").fill("USD");
  await activate(page, panel.getByRole("button", { name: startsWith(currency("USD")) }));
  await shows(segment(panel, copy.settings.app.currency), "USD");
  await record("overrode the currency with USD");
  await shot(page, `${language}-3-currency-overridden-usd`);

  await page.reload({ waitUntil: "networkidle" });
  panel = await openPanel(page, copy);
  await shows(segment(panel, copy.settings.app.country), region("MX"));
  await shows(segment(panel, copy.settings.app.currency), "USD");
  await record("after a reload");
  await shot(page, `${language}-4-after-reload`);

  // The picker sends the Dominican Republic; the request is rewritten to a
  // region that is not a country, so the refusal is the API's own 422.
  await page.route("**/api/v1/me", async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.continue({ postData: JSON.stringify({ country: "EU" }) });
  });
  const refusal = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && response.url().endsWith("/api/v1/me"),
  );
  await panel.getByRole("textbox").fill(region("DO"));
  await activate(page, panel.getByRole("button", { name: startsWith(region("DO")) }));
  const status = (await refusal).status();
  await panel.getByRole("alert").waitFor();
  await shows(segment(panel, copy.settings.app.country), region("MX"));
  await record("refused save shown and put back", {
    patch_status: status,
    alert: await panel.getByRole("alert").innerText(),
  });
  await shot(page, `${language}-5-refused-save-put-back`);
  await page.unroute("**/api/v1/me");

  report[`${language}_page_errors`] = errors;
  await context.close();
}
await browser.close();
writeFileSync(`${OUT}/report.json`, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
