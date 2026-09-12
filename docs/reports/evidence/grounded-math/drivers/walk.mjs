// Browser evidence for Any grounded math: every scene the item's proof names,
// in English and Spanish at 1280 and 390 CSS pixels, against the local web app
// (3620) and API (8620). Scenes read conversation ids from the seed file and the
// recorded smoke turns. The only writes are the ones a user makes on screen:
// a recompute, a decision, a comparison, a continued chat, a share, a search.
// Usage: GM_TREE=<tree> GM_SEEDS=<seeds.json> [GM_SCENES=a,b] [GM_LANGUAGES=en] node walk.mjs
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const TREE = process.env.GM_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/grounded-math/browser`;
const TURNS = `${TREE}/docs/reports/evidence/grounded-math/turns`;
mkdirSync(OUT, { recursive: true });
const API = `http://127.0.0.1:${process.env.GM_API_PORT || "8620"}/api/v1`;
const WEB = `http://127.0.0.1:${process.env.GM_WEB_PORT || "3620"}`;
const SEEDS = JSON.parse(readFileSync(process.env.GM_SEEDS, "utf-8"));
const WANTED = (process.env.GM_SCENES || "").split(",").filter(Boolean);
const LANGUAGES = (process.env.GM_LANGUAGES || "en,es-419").split(",");
const WIDTHS = [[1280, 900], [390, 844]];
const MOD = process.platform === "darwin" ? "Meta" : "Control";
const COPY = {
  en: { addDecision: "Add decision", watching: "Watching", save: "Save decision", run: "Run backtest", ask: "zanzibar trip fund with 300 saved every month" },
  "es-419": { addDecision: "Agregar decisión", watching: "Observando", save: "Guardar decisión", run: "Ejecutar backtest", ask: "fondo para un viaje a zanzíbar ahorrando 300 cada mes" },
};
const report = [];
const receipts = {};

async function api(path, init = {}) {
  const response = await fetch(`${API}${path}`, { ...init, headers: { "content-type": "application/json", ...(init.headers || {}) } });
  const text = await response.text();
  if (!response.ok) throw new Error(`${init.method || "GET"} ${path} ${response.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

async function setProfile(language) {
  const country = language === "es-419" ? "DO" : "US";
  await api("/me", { method: "PATCH", body: JSON.stringify({ language, country }) })
    .catch(() => api("/me", { method: "PATCH", body: JSON.stringify({ language }) }));
}

function turn(id, language) {
  const path = `${TURNS}/${id}-${language}.json`;
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf-8")) : null;
}

/** The first smoke turn whose last reply stored a card that solved. */
function computedTurn(language, preferCited = false) {
  const order = preferCited ? ["q6", "q4", "q1", "q2", "q8", "q3", "q7", "q5"] : ["q1", "q3", "q6", "q2", "q4", "q8", "q7", "q5"];
  for (const id of order) {
    const record = turn(id, language);
    const last = record?.turns?.at(-1);
    if (last?.summary?.status !== "succeeded") continue;
    if (preferCited && !last.summary.inputs?.some((input) => input.source === "page")) continue;
    return { id, record, last };
  }
  return preferCited ? computedTurn(language, false) : null;
}

async function open(tab, conversationId) {
  await tab.goto(`${WEB}/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
  await tab.waitForTimeout(2500);
  await tab.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
}

async function shot(tab, name, width, language, extra = {}, fullPage = true) {
  const file = `${name}-${width}-${language}.png`;
  await tab.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
  await tab.screenshot({ path: `${OUT}/${file}`, fullPage });
  return { screenshot: file, ...extra };
}

async function editFirstInput(tab, factor) {
  const input = tab.locator("[data-tool-result-card] [data-tool-input] input:not([disabled])").first();
  await input.scrollIntoViewIfNeeded();
  const before = await input.inputValue();
  const next = String(Math.round((Number(before) || 1) * factor * 100) / 100);
  const done = tab.waitForResponse((response) => response.url().includes("/recompute") && response.request().method() === "POST", { timeout: 30000 });
  await input.fill(next);
  const response = await done;
  await tab.waitForTimeout(1500);
  return { from: before, to: next, status: response.status() };
}

const browser = await chromium.launch();

async function scene(name, run) {
  if (WANTED.length && !WANTED.includes(name)) return;
  for (const language of LANGUAGES) {
    await setProfile(language);
    for (const [width, height] of WIDTHS) {
      const context = await browser.newContext({ viewport: { width, height }, isMobile: width < 768, hasTouch: width < 768, deviceScaleFactor: 2, locale: language === "es-419" ? "es-419" : "en-US" });
      const tab = await context.newPage();
      const errors = [];
      tab.on("pageerror", (error) => errors.push(String(error)));
      const entry = { scene: name, language, width };
      try {
        Object.assign(entry, (await run({ tab, width, language, copy: COPY[language] })) || {});
        entry.ok = true;
      } catch (error) {
        entry.ok = false;
        entry.error = String(error).slice(0, 500);
        try { entry.failure_shot = (await shot(tab, `${name}-failed`, width, language)).screenshot; } catch {}
      }
      entry.page_errors = errors;
      report.push(entry);
      console.log(JSON.stringify(entry));
      await context.close();
    }
  }
}

await scene("answers", async ({ tab, width, language }) => {
  const shots = [];
  for (const id of ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q10"]) {
    const record = turn(id, language);
    if (!record) continue;
    await open(tab, record.conversation_id);
    shots.push((await shot(tab, `answer-${id}`, width, language)).screenshot);
  }
  return { shots };
});

await scene("backtest", async ({ tab, width, language, copy }) => {
  const record = turn("q9", language);
  if (!record) throw new Error("no recorded q9 turn");
  await open(tab, record.conversation_id);
  const run = tab.getByRole("button", { name: copy.run });
  let ran = false;
  if (await run.count()) {
    await run.first().click();
    ran = true;
    await tab.waitForFunction((label) => ![...document.querySelectorAll("button")].some((button) => button.textContent?.includes(label)), copy.run, { timeout: 240000 });
    await tab.waitForTimeout(8000);
  }
  return shot(tab, "backtest", width, language, { ran });
});

await scene("recompute", async ({ tab, width, language }) => {
  const found = computedTurn(language);
  if (!found) throw new Error("no computed smoke turn");
  await open(tab, found.record.conversation_id);
  const edit = await editFirstInput(tab, 1.1);
  return shot(tab, "recompute", width, language, { turn: found.id, ...edit });
});

await scene("decision", async ({ tab, width, language, copy }) => {
  const found = computedTurn(language);
  if (!found) throw new Error("no computed smoke turn");
  await open(tab, found.record.conversation_id);
  let area = tab.locator('[data-testid="computed-answer-decision"]').first();
  if (!(await area.locator('[data-testid="open-decision"]').count())) {
    await area.getByRole("button", { name: copy.addDecision }).click();
    await area.getByRole("button", { name: copy.watching }).click();
    const saved = tab.waitForResponse((response) => response.url().includes("/decision") && response.request().method() === "POST");
    await area.getByRole("button", { name: copy.save }).click();
    await saved;
    await tab.waitForTimeout(1000);
  }
  const edit = await editFirstInput(tab, 1.2);
  await open(tab, found.record.conversation_id);
  area = tab.locator('[data-testid="computed-answer-decision"]').first();
  await area.locator('[data-testid="open-decision"]').click();
  await tab.waitForSelector('[data-testid="computed-rerun-panel"]', { timeout: 20000 });
  await tab.waitForTimeout(1500);
  const reopened = await shot(tab, "decision-reopened", width, language, { turn: found.id, ...edit });
  const storedInput = tab.locator('[data-testid="computed-rerun-panel"] [data-computed-rerun="stored"] input:not([disabled])').first();
  const original = await storedInput.inputValue();
  await storedInput.fill(String((Number(original) || 1) + 1));
  await storedInput.fill(original);
  await tab.waitForSelector('[data-testid="computed-rerun-up-to-date"]', { timeout: 5000 });
  const upToDate = await shot(tab, "failure-up-to-date", width, language);
  return { ...reopened, up_to_date: upToDate.screenshot };
});

await scene("decision-cannot-rerun", async ({ tab, width, language }) => {
  const seed = SEEDS[`stale-decision-${language}`];
  await open(tab, seed.conversation_id);
  const opened = tab.waitForResponse((response) => response.url().includes(`/decisions/${seed.decision_id}`), { timeout: 20000 });
  await tab.locator('[data-testid="open-decision"]').first().click();
  await opened;
  await tab.waitForTimeout(1500);
  return shot(tab, "failure-decision-cannot-rerun", width, language);
});

await scene("outage", async ({ tab, width, language }) => {
  await open(tab, SEEDS[`outage-${language}`].conversation_id);
  await tab.waitForSelector('[data-tool-outcome-tone="retryable"]', { timeout: 15000 });
  return shot(tab, "failure-outage", width, language);
});

await scene("withheld", async ({ tab, width, language }) => {
  await open(tab, SEEDS[`withheld-${language}`].conversation_id);
  await tab.waitForSelector("[data-tool-result-card]", { timeout: 15000 });
  return shot(tab, "failure-withheld", width, language);
});

await scene("no-solution", async ({ tab, width, language }) => {
  await open(tab, SEEDS[`no-solution-${language}`].conversation_id);
  const repair = tab.locator("[data-tool-repair]").first();
  await repair.waitFor({ timeout: 15000 });
  const before = await shot(tab, "failure-no-solution", width, language);
  const done = tab.waitForResponse((response) => response.url().includes("/recompute"), { timeout: 30000 });
  await repair.click();
  await done;
  await tab.waitForTimeout(1500);
  return { ...before, repaired: (await shot(tab, "failure-no-solution-repaired", width, language)).screenshot };
});

await scene("rail", async ({ tab, width, language }) => {
  await open(tab, SEEDS[`rail-${language}`].conversation_id);
  if (width < 768) return shot(tab, "rail-hidden-below-tablet", width, language, {}, false);
  const tick = tab.locator('[data-testid="conversation-activity-rail"] nav button').first();
  await tick.hover();
  await tab.waitForTimeout(700);
  return shot(tab, "rail-result", width, language, { label: await tick.getAttribute("aria-label") }, false);
});

await scene("search-dossier", async ({ tab, width, language }) => {
  const found = computedTurn(language, true);
  if (!found) throw new Error("no computed smoke turn");
  await open(tab, found.record.conversation_id);
  await tab.keyboard.press(`${MOD}+k`);
  await tab.waitForSelector('input[maxlength="512"]', { timeout: 10000 });
  const words = found.last.message.split(/[^\p{L}\p{N}]+/u).filter((word) => word.length >= 4);
  const query = words.sort((left, right) => right.length - left.length)[0];
  await tab.keyboard.type(query);
  await tab.waitForTimeout(3000);
  await tab.locator("[data-palette-row-index]").first().click();
  await tab.waitForSelector("[data-answer-dossier]", { timeout: 15000 }).catch(() => {});
  await tab.waitForTimeout(1500);
  return shot(tab, "search-dossier", width, language, { turn: found.id, query }, false);
});

await scene("compare-continue", async ({ tab, width, language }) => {
  await open(tab, SEEDS[`rail-${language}`].conversation_id);
  const actions = tab.locator("[data-computed-answer-actions]").first();
  await actions.scrollIntoViewIfNeeded();
  await actions.locator('[data-compute-action="compare"]').click();
  await tab.locator("[data-compare-choice]").first().waitFor({ timeout: 15000 });
  await tab.locator("[data-compare-choice]").first().click();
  await tab.waitForSelector("[data-computation-comparison]", { timeout: 15000 });
  await tab.locator("[data-computation-comparison]").scrollIntoViewIfNeeded();
  await tab.waitForTimeout(800);
  const compared = await shot(tab, "compare", width, language);
  await actions.locator('[data-compute-action="continue"]').click();
  await tab.waitForSelector("[data-continued-from]", { timeout: 20000 });
  await tab.waitForTimeout(1500);
  return { ...compared, continued: (await shot(tab, "continue", width, language)).screenshot };
});

await scene("receipt", async ({ tab, width, language }) => {
  if (!receipts[language]) {
    const found = computedTurn(language, true);
    if (!found) throw new Error("no computed smoke turn");
    const conversationId = found.record.conversation_id;
    const candidates = await api(`/conversations/${conversationId}/public-excerpt-candidates`);
    const item = candidates.items.find((candidate) => candidate.eligible && candidate.kind === "calculation");
    if (!item) throw new Error(`no eligible calculation: ${JSON.stringify(candidates.items)}`);
    const selection = { message_ids: [item.message_id], owner_note: null };
    const preview = await api(`/conversations/${conversationId}/public-excerpt-preview`, { method: "POST", body: JSON.stringify(selection) });
    const created = await api(`/conversations/${conversationId}/public-excerpt`, { method: "POST", body: JSON.stringify({ ...selection, payload_digest: preview.payload_digest }) });
    receipts[language] = created.receipt.path;
  }
  await tab.context().clearCookies();
  await tab.goto(`${WEB}${receipts[language]}`, { waitUntil: "networkidle" });
  await tab.waitForTimeout(2500);
  return shot(tab, "receipt-signed-out", width, language, { path: receipts[language] });
});

await scene("ask-argus", async ({ tab, width, language, copy }) => {
  await tab.goto(`${WEB}/chat`, { waitUntil: "networkidle" });
  await tab.waitForTimeout(2500);
  await tab.keyboard.press(`${MOD}+k`);
  await tab.waitForSelector('input[maxlength="512"]', { timeout: 10000 });
  await tab.keyboard.type(copy.ask);
  await tab.waitForSelector("[data-ask-argus-row]", { timeout: 20000 });
  const row = await shot(tab, "ask-argus-row", width, language, {}, false);
  if (width !== 1280) return row;
  await tab.keyboard.press("Enter");
  await tab.waitForTimeout(60000);
  return { ...row, sent: (await shot(tab, "ask-argus-sent", width, language)).screenshot };
});

await browser.close();
writeFileSync(`${OUT}/${process.env.GM_REPORT || "walk-report.json"}`, JSON.stringify(report, null, 2) + "\n");
console.log(`scenes ${report.length}, failed ${report.filter((entry) => !entry.ok).length}`);
