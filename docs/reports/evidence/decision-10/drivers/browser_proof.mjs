// Browser proof for decision 10: opens the recorded conversations in the web
// app and screenshots the answer at 1280 and 390 CSS pixels in the language
// the question was asked in. Local web 3610 against the local API on 8610.
// Usage: D10_TREE=<tree> D10_AFTER=<after_dir> node browser_proof.mjs
import { createRequire } from "node:module";
import { readFileSync, mkdirSync, writeFileSync, readdirSync } from "node:fs";

const TREE = process.env.D10_TREE;
const AFTER = process.env.D10_AFTER;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/decision-10/browser`;
mkdirSync(OUT, { recursive: true });
const API = `http://127.0.0.1:${process.env.D10_API_PORT || "8610"}/api/v1`;
const WEB = `http://127.0.0.1:${process.env.D10_WEB_PORT || "3610"}`;
const WANTED = (process.env.D10_PROOF_IDS || "nvda-future-value,nvda-grow-into,savings-500-5pct,nvda-future-value-es,nvda-grow-into-es,ahorro-5000-6pct").split(",");

async function setLanguage(language) {
  const response = await fetch(`${API}/me`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ language }) });
  if (!response.ok) throw new Error(`PATCH /me ${response.status} ${await response.text()}`);
}

const browser = await chromium.launch();
const report = [];
for (const file of readdirSync(AFTER).filter((name) => name.endsWith(".json"))) {
  const record = JSON.parse(readFileSync(`${AFTER}/${file}`, "utf-8"));
  if (!WANTED.includes(record.label)) continue;
  await setLanguage(record.language);
  for (const [width, height] of [[1280, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, isMobile: width < 768, deviceScaleFactor: 2, locale: record.language === "es-419" ? "es-419" : "en-US" });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));
    await page.goto(`${WEB}/chat?conversation=${record.conversation_id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
    const path = `${OUT}/${record.label}-${width}-${record.language}.png`;
    await page.screenshot({ path, fullPage: true });
    const text = await page.locator("main").innerText().catch(() => "");
    report.push({ label: record.label, language: record.language, width, screenshot: path.split("/").slice(-1)[0], errors, textChars: text.length, mentionsScenario: /scenario|escenario/i.test(text), mentionsCannotPredict: /can't predict|cannot predict|no puedo predecir/i.test(text) });
    await context.close();
  }
}
await browser.close();
writeFileSync(`${OUT}/${process.env.D10_REPORT || "report.json"}`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
