// Issue #440 browser journey: idea -> drawer date edit -> cancel -> stated
// duration follow-up. Frames land in QA_OUT as <QA_TAG>-<step>.png; the
// conversation's persisted messages are dumped beside them for inspection.
// QA_SKIP_DRAWER=1 runs the control journey without the drawer edit.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = "http://127.0.0.1:3011";
const API = "http://127.0.0.1:8010/api/v1";
const OUT = process.env.QA_OUT;
const TAG = process.env.QA_TAG || "run";
const FOLLOWUP = process.env.QA_FOLLOWUP || "Run that Apple idea again for the last six months";
const LANG = process.env.QA_LANG || "en";
const IDEA = process.env.QA_IDEA || "Buy and hold Apple for the last year with $10,000";
const L = LANG === "en"
  ? { dates: "Edit dates", apply: "Apply", send: "Send message", cancel: "Cancel", run: "Run backtest" }
  : { dates: "Editar fechas", apply: "Aplicar", send: "Enviar mensaje", cancel: "Cancelar", run: "Ejecutar backtest" };
if (!OUT) throw new Error("QA_OUT is required");
mkdirSync(OUT, { recursive: true });

const shot = (page, tag) => page.screenshot({ path: `${OUT}/${TAG}-${tag}.png`, fullPage: false });

async function sendMessage(page, text) {
  const composer = page.getByRole("combobox").first();
  await composer.click();
  await page.keyboard.type(text, { delay: 8 });
  await page.getByRole("button", { name: L.send }).click();
}
async function waitForPill(page) {
  await page.getByRole("button", { name: L.dates }).last().waitFor({ state: "visible", timeout: 120_000 });
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await context.addInitScript((lang) => { window.localStorage.setItem("i18nextLng", lang); }, LANG);
const page = await context.newPage();
page.setDefaultTimeout(120_000);
await page.request.patch(`${API}/me`, { data: { language: LANG } });
await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });

await sendMessage(page, IDEA);
await waitForPill(page);
await page.waitForTimeout(600);
await shot(page, "1-card");

if (!process.env.QA_SKIP_DRAWER) {
  await page.getByRole("button", { name: L.dates }).last().click();
  const startInput = page.locator('input[type="date"]').first();
  await startInput.waitFor({ state: "visible" });
  await startInput.fill("2024-08-11");
  await shot(page, "2-dates-drawer");
  await page.getByRole("button", { name: L.apply }).last().click();
  await page.waitForTimeout(1500);
  await shot(page, "3-dates-applied");
}

await page.getByRole("button", { name: L.cancel }).last().click();
await page.waitForTimeout(2500);
await shot(page, "4-cancelled");

await sendMessage(page, FOLLOWUP);
// A fresh card settles the turn; the cancelled card has no pills left.
await waitForPill(page);
await page.waitForTimeout(1200);
await shot(page, "5-followup");
const text = await page.locator("main").innerText().catch(() => page.locator("body").innerText());
writeFileSync(`${OUT}/${TAG}-page.txt`, text);

const url = page.url();
const convs = await (await page.request.get(`${API}/conversations?limit=5`)).json();
writeFileSync(`${OUT}/${TAG}-conversations.json`, JSON.stringify(convs, null, 2));
const items = convs.items || convs.data || convs.conversations || [];
const conv = items[0];
if (conv) {
  const msgs = await (await page.request.get(`${API}/conversations/${conv.id}/messages?limit=50`)).json();
  writeFileSync(`${OUT}/${TAG}-messages.json`, JSON.stringify(msgs, null, 2));
  console.log("conversation", conv.id, "messages", (msgs.items || msgs.data || []).length);
}
console.log("url", url);
await context.close();
await browser.close();
