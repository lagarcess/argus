// Headless capture of the Spanish confirmation replay: screenshots, visible
// text and the reader transport. Run from the repository root with node.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const require = createRequire(path.join(root, "web/package.json"));
const { chromium } = require("@playwright/test");

const WEB = process.env.REPLAY_WEB_ORIGIN ?? "http://127.0.0.1:3293";
const API = process.env.REPLAY_API ?? "http://127.0.0.1:8593/api/v1";
const OUT = process.env.EVIDENCE_OUT ?? path.join(root, "temp/evidence-after");
mkdirSync(OUT, { recursive: true });

const manifest = JSON.parse(readFileSync(path.join(root, "temp/replay-manifest.json"), "utf8"));
const byShape = Object.fromEntries(manifest.conversations.map((c) => [c.shape, c]));
const report = { head: manifest.head, captured_at_utc: new Date().toISOString(), captures: [] };

async function api(pathname, init) {
  const response = await fetch(`${API}${pathname}`, init);
  return { status: response.status, body: await response.json() };
}

function cardTurn(items) {
  return items.find((item) => item.role === "assistant" && item.metadata?.confirmation_card);
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "es-419" });
const page = await context.newPage();
const consoleErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});

async function capture(shape, label) {
  const conversation = byShape[shape];
  await page.goto(`${WEB}/chat?conversation=${conversation.conversation_id}`);
  await page.locator("[data-confirmation-status]").first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(1200);
  const visibleText = await page.evaluate(() => document.body.innerText);
  const html = await page.evaluate(() => document.documentElement.outerHTML);
  const screenshot = `${label}.png`;
  await page.screenshot({ path: path.join(OUT, screenshot) });
  const messages = await api(`/conversations/${conversation.conversation_id}/messages`);
  writeFileSync(path.join(OUT, `${label}-messages.json`), JSON.stringify(messages.body, null, 2));
  const turn = cardTurn(messages.body.items ?? []);
  const record = {
    label,
    shape,
    conversation_id: conversation.conversation_id,
    screenshot,
    html_lang: await page.evaluate(() => document.documentElement.lang),
    dom_contains_ready_to_test: html.includes("Ready to test"),
    transport_card_turn_content: turn?.content ?? null,
    transport_card_has_summary: Boolean(turn && "summary" in turn.metadata.confirmation_card),
    visible_text: visibleText,
  };
  report.captures.push(record);
  return record;
}

await capture("buy_and_hold", "es-buy-and-hold-card");
await capture("recurring_buys", "es-recurring-buys-card");
await capture("rsi_threshold", "es-rsi-threshold-card");
await capture("legacy_buy_and_hold", "es-legacy-card-turn");

// The real in-place edit path rebuilds and persists the card, the same writer
// the drawer uses.
const buyAndHold = byShape.buy_and_hold;
const edit = await api(
  `/conversations/${buyAndHold.conversation_id}/confirmations/${buyAndHold.confirmation_id}/direct-edit`,
  { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ capital: 25000 }) },
);
report.direct_edit = {
  status: edit.status,
  response_content: edit.body?.message?.content ?? null,
  response_card_has_summary: Boolean(edit.body?.message && "summary" in edit.body.message.metadata.confirmation_card),
};
await capture("buy_and_hold", "es-buy-and-hold-card-after-in-place-edit");

const conversations = await api("/conversations?limit=30&archived=false&deleted=false");
writeFileSync(path.join(OUT, "conversations.json"), JSON.stringify(conversations.body, null, 2));
const search = await api(`/search?q=${encodeURIComponent("AAPL")}`);
writeFileSync(path.join(OUT, "search-aapl.json"), JSON.stringify(search.body, null, 2));
report.console_errors = consoleErrors;
writeFileSync(path.join(OUT, "capture-report.json"), JSON.stringify(report, null, 2));
await browser.close();
console.log(JSON.stringify({
  direct_edit: report.direct_edit,
  captures: report.captures.map(({ visible_text, ...rest }) => rest),
  console_errors: consoleErrors.length,
}, null, 2));
