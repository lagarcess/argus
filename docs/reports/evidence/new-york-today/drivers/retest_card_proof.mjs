// Retests a seeded run from the command palette on the frozen-clock backend and
// captures the confirmation card. Usage: node retest_card_proof.mjs <lang> <seed.json> <outDir>
import { createRequire } from "node:module";
import fs from "node:fs";

const require = createRequire(`${process.env.ARGUS_WEB_DIR}/package.json`);
const { chromium } = require("@playwright/test");

const [lang, seedPath, outDir] = process.argv.slice(2);
const API = process.env.ARGUS_API_URL ?? "http://127.0.0.1:8017/api/v1";
const WEB = process.env.ARGUS_WEB_URL ?? "http://localhost:3017";
const seed = JSON.parse(fs.readFileSync(seedPath, "utf-8"));
const { symbol, conversation_id: conversationId } = seed.conversations[lang];
const copy = {
  en: {
    search: "Search Argus...",
    retest: "Retest with current data",
    compactEnd: "Sep 9, 2026",
  },
  "es-419": {
    search: "Buscar en Argus...",
    retest: "Volver a probar con datos actuales",
    compactEnd: "9 sept 2026",
  },
}[lang];
fs.mkdirSync(outDir, { recursive: true });
const step = (name) => console.log(`[${lang}] ${name}`);

const profile = await fetch(`${API}/me`, {
  method: "PATCH",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ language: lang }),
});
step(`PATCH /me language=${lang} -> ${profile.status}`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
try {
  await page.goto(`${WEB}/chat`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.keyboard.press("Meta+k");
  const search = page.getByPlaceholder(copy.search);
  await search.waitFor({ timeout: 10000 });
  await search.fill(symbol);
  const retest = page.getByRole("button", { name: copy.retest });
  await retest.waitFor({ timeout: 20000 });
  await retest.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${outDir}/${lang}-1-dossier.png` });
  step("dossier offers retest");
  await retest.click();
  const period = page.getByText(copy.compactEnd, { exact: false }).last();
  await period.waitFor({ timeout: 45000 });
  await period.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${outDir}/${lang}-2-confirmation-card.png` });

  const messages = await (
    await fetch(`${API}/conversations/${conversationId}/messages?limit=100`)
  ).json();
  const card = messages.items
    .map((message) => message.metadata?.confirmation_card)
    .filter(Boolean)
    .at(-1);
  const report = {
    language: lang,
    symbol,
    frozen_at: seed.frozen_at,
    process_tz: seed.process_tz,
    host_date: seed.host_date,
    new_york_date: seed.new_york_date,
    rendered_compact_end: copy.compactEnd,
    rendered_period_lines: (await page.locator("main").innerText())
      .split("\n")
      .filter((line) => line.includes("2026")),
    persisted_period_row: card?.rows?.find((row) => row.key === "period")?.value,
    persisted_effective_date_range: card?.retest_period?.effective_date_range,
  };
  fs.writeFileSync(`${outDir}/${lang}-report.json`, `${JSON.stringify(report, null, 2)}\n`);
  step(`persisted period: ${report.persisted_period_row}`);
  step(`effective range: ${JSON.stringify(report.persisted_effective_date_range)}`);
} catch (error) {
  await page.screenshot({ path: `${outDir}/${lang}-error.png` });
  console.log(`[${lang}] ERROR ${error.message.split("\n")[0]}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
