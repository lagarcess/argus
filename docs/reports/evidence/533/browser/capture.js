// Headless Playwright capture for #533: the result card, its Quick Take, and
// the Try next reason on one screen, in English and Spanish.
// usage: NODE_PATH=<web>/node_modules node capture_533.js <webOrigin> <apiOrigin> <outDir> <label>
const { createRequire } = require("node:module");
const fs = require("node:fs");
const path = require("node:path");
const [webOrigin, apiOrigin, outDir, label] = process.argv.slice(2);
const require2 = createRequire(process.env.WEB_PACKAGE_JSON);
const { chromium } = require2("@playwright/test");

const LANGS = {
  en: { language: "en", locale: "en-US", recents: "Recents", quickTake: "Quick take" },
  "es-419": { language: "es-419", locale: "es-419", recents: "Recientes", quickTake: "Lectura rápida" },
};
const TITLE = "META Buy and Hold Strategy";

async function capture(lang) {
  const cfg = LANGS[lang];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1500 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  // Workspace language: persisted profile plus the i18next storage key.
  await page.goto(`${webOrigin}/chat`, { waitUntil: "domcontentloaded" });
  const patched = await page.request.patch(`${apiOrigin}/me`, { data: { language: cfg.language, locale: cfg.locale } });
  if (!patched.ok()) throw new Error(`PATCH /me failed: ${patched.status()}`);
  await page.evaluate((code) => localStorage.setItem("i18nextLng", code), lang);
  await page.reload({ waitUntil: "networkidle" });
  // Open the recorded conversation from Recents (no deep link exists).
  await page.getByRole("button", { name: cfg.recents }).first().click();
  await page.getByText(TITLE, { exact: false }).first().click();
  await page.getByText(cfg.quickTake, { exact: false }).first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(1500);
  const main = page.locator("main").first();
  const text = await main.innerText();
  fs.writeFileSync(path.join(outDir, `${label}-${lang}-visible-text.txt`), text + "\n");
  await page.screenshot({ path: path.join(outDir, `${label}-${lang}.png`), fullPage: true });
  await browser.close();
  return { consoleErrors, text };
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const summary = {};
  for (const lang of Object.keys(LANGS)) {
    const { consoleErrors, text } = await capture(lang);
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    const pick = (re) => lines.filter((l) => re.test(l));
    summary[lang] = {
      console_errors: consoleErrors,
      card_benchmark: pick(/percentage points|puntos porcentuales/i).filter((l) => !/ahead of|behind|por encima|por debajo/i.test(l)),
      quick_take: pick(/ahead of|behind|por encima|por debajo|in line with|al mismo nivel/i),
      try_next_reason: pick(/Beat the benchmark|Lagged the benchmark|Superó la referencia|por debajo de la referencia|Worst drop was|La peor caída fue/i),
      worst_drop: pick(/^-?\d+\.\d%$/),
    };
  }
  fs.writeFileSync(path.join(outDir, `${label}-summary.json`), JSON.stringify(summary, null, 2) + "\n");
  console.log(JSON.stringify(summary, null, 2));
})().catch((error) => { console.error(error); process.exit(1); });
