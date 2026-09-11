// Browser proof for #590: the production repro driven in the real web app
// against the local live API (serve.py on 8590, web dev server on 3590), once
// per workspace language. Turn 1 asks for the Apple buy-and-hold test and runs
// it from the confirmation card; turn 2 asks what to try next. The proof is
// the lead-in plus the Try next rows on the follow-up message, and no retry
// recovery. Screenshots at 1280 and 390 CSS pixels. Paid: real interpreter,
// composer and market-data turns.
// Usage: I590_TREE=<tree> node browser_demo.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const TREE = process.env.I590_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/issue-590/browser`;
mkdirSync(OUT, { recursive: true });
const API = `http://127.0.0.1:${process.env.I590_API_PORT || "8590"}/api/v1`;
const WEB = `http://127.0.0.1:${process.env.I590_WEB_PORT || "3590"}`;

const SCRIPT = {
  en: {
    question: "What if I just bought and held Apple through 2024?",
    run: "Run backtest",
    quickTake: "Quick take",
    followup: "ok what should I try next?",
    tryNext: "Try next",
    dateRow: "Test a different date range",
    recovery: /couldn.t answer that follow-up/i,
  },
  "es-419": {
    question: "¿Y si simplemente hubiera comprado y mantenido Apple durante 2024?",
    run: "Ejecutar backtest",
    quickTake: "Lectura rápida",
    followup: "ok, ¿qué debería probar después?",
    tryNext: "Qué probar después",
    dateRow: "Probar otro rango de fechas",
    recovery: /No pude responder ese seguimiento/i,
  },
};

async function setLanguage(language) {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status} ${await response.text()}`);
}

async function composerEnabled(page, timeout = 240000) {
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="chat-input"]');
      return el !== null && el.getAttribute("aria-disabled") !== "true";
    },
    undefined,
    { timeout },
  );
}

async function send(page, message) {
  await composerEnabled(page);
  const composer = page.locator('[role="combobox"], textarea').first();
  await composer.click();
  await composer.fill(message);
  await page.locator('button[type="submit"]').first().click();
}

// textContent, not innerText: the section labels are uppercased by CSS and
// innerText would return "QUICK TAKE" for the DOM's "Quick take".
async function mainText(page) {
  return (await page.evaluate(() => document.querySelector("main")?.textContent ?? "")).replace(/\s+/g, " ");
}

async function waitForText(page, needle, timeout = 240000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if ((await mainText(page)).includes(needle)) return;
    await page.waitForTimeout(1500);
  }
  throw new Error(`timed out waiting for "${needle}"`);
}

async function settled(page, timeout = 180000) {
  const started = Date.now();
  let last = "";
  let stable = 0;
  while (Date.now() - started < timeout) {
    const text = await mainText(page);
    if (text === last) {
      stable += 1;
      if (stable >= 3) return;
    } else {
      stable = 0;
    }
    last = text;
    await page.waitForTimeout(1500);
  }
}

const browser = await chromium.launch();
const report = [];
for (const [language, script] of Object.entries(SCRIPT)) {
  await setLanguage(language);
  const locale = language === "es-419" ? "es-419" : "en-US";
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, locale });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  const timings = {};
  let t = Date.now();
  await page.goto(`${WEB}/chat`, { waitUntil: "networkidle" });
  await page.waitForSelector('[role="combobox"], textarea', { timeout: 60000 });
  await page.waitForTimeout(1500);

  await send(page, script.question);
  await waitForText(page, script.run);
  timings.confirmation_seconds = Math.round((Date.now() - t) / 100) / 10;
  await page.waitForTimeout(800);
  await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
  await page.screenshot({ path: `${OUT}/${language}-1-confirmation-1280.png`, fullPage: true });

  t = Date.now();
  await page.getByRole("button", { name: script.run }).first().click();
  await waitForText(page, script.quickTake);
  await composerEnabled(page);
  await settled(page);
  timings.result_seconds = Math.round((Date.now() - t) / 100) / 10;
  await page.screenshot({ path: `${OUT}/${language}-2-result-1280.png`, fullPage: true });

  t = Date.now();
  await send(page, script.followup);
  await waitForText(page, script.followup);
  await composerEnabled(page);
  await settled(page);
  timings.followup_seconds = Math.round((Date.now() - t) / 100) / 10;
  await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
  await page.screenshot({ path: `${OUT}/${language}-3-what-next-1280.png`, fullPage: true });

  const text = await mainText(page);
  const sections = page.locator(`section[aria-label="${script.tryNext}"]`);
  const sectionCount = await sections.count();
  const rows = sectionCount
    ? await sections.last().locator("button").allInnerTexts()
    : [];

  // Step 4: a continuity row tapped from the follow-up message must submit the
  // typed refine action anchored on the run, not its label as prose.
  const sent = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/chat/stream") && request.method() === "POST") {
      try { sent.push(JSON.parse(request.postData() || "{}")); } catch { sent.push({ unparsed: true }); }
    }
  });
  // When the structured tier is unavailable the turn has no typed focus and
  // the interpreter-unavailable path answers in composer prose with no rows;
  // record that instead of failing the run, so the report says which path ran.
  let dateRowRequest = null;
  let afterDateRow = "";
  const dateRow = sectionCount
    ? sections.last().getByRole("button", { name: script.dateRow }).first()
    : null;
  if (dateRow && (await dateRow.count()) > 0) {
    t = Date.now();
    await dateRow.click();
    await composerEnabled(page);
    await settled(page);
    timings.date_row_seconds = Math.round((Date.now() - t) / 100) / 10;
    await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
    await page.screenshot({ path: `${OUT}/${language}-4-date-row-1280.png`, fullPage: true });
    dateRowRequest = sent[0] ? { message: sent[0].message, action: sent[0].action ?? sent[0].structured_action ?? null } : null;
    afterDateRow = (await page.locator('[data-testid="conversation-transcript-region"]').innerText().catch(() => "")).replace(/\s+/g, " ");
  }
  const messages = await page.locator('[data-testid="conversation-transcript-region"]').innerText().catch(() => text);
  const followupIndex = messages.lastIndexOf(script.followup);
  const afterFollowup = followupIndex >= 0 ? messages.slice(followupIndex + script.followup.length) : messages;
  const conversationId = new URL(page.url()).searchParams.get("conversation");

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 2, locale });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(`${WEB}/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
  await mobilePage.waitForTimeout(2500);
  await mobilePage.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
  await mobilePage.screenshot({ path: `${OUT}/${language}-3-what-next-390.png`, fullPage: true });
  await mobile.close();

  report.push({
    language,
    conversation_id: conversationId,
    timings,
    try_next_sections: sectionCount,
    rows,
    after_followup_text: afterFollowup.replace(/\s+/g, " ").trim().slice(0, 600),
    recovery_shown: script.recovery.test(text),
    followup_typed_next_experiment: sectionCount > 0,
    date_row_request: dateRowRequest,
    after_date_row_text: afterDateRow ? afterDateRow.slice(afterDateRow.lastIndexOf(script.dateRow)).slice(0, 500) : null,
    page_errors: errors,
    screenshots: [1, 2, 3, 4].map((n) => `${language}-${n}-*.png`),
  });
  console.log(JSON.stringify(report[report.length - 1], null, 2));
  await context.close();
}
await browser.close();
writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2) + "\n");
