// Browser drive for the open-the-gates lane: the Nike quote's share screen,
// the same in Spanish for the Apple quote, and the full share flow (select,
// preview, create, open signed out) on the NVIDIA answer that has publisher
// sources. Local web 3590 against the local memory-mode API on 8590.
import { createRequire } from "node:module";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";

const TREE = process.env.OTG_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/open-the-gates/browser`;
mkdirSync(OUT, { recursive: true });
const API = "http://127.0.0.1:8590/api/v1";
const WEB = "http://127.0.0.1:3590";
const copyFor = (language) => JSON.parse(readFileSync(`${TREE}/web/public/locales/${language}/common.json`, "utf-8")).receipt;
const conversationOf = (file) => JSON.parse(readFileSync(`${TREE}/docs/reports/evidence/open-the-gates/after/${file}`, "utf-8")).conversation_id;
const NIKE = conversationOf("argus-nike.json");
const NVDA = conversationOf("argus-nvda-week.json");
const APPLE_ES = conversationOf("argus-apple-es.json");

async function setLanguage(language) {
  const response = await fetch(`${API}/me`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ language }) });
  if (!response.ok) throw new Error(`PATCH /me ${response.status} ${await response.text()}`);
}
async function openChat(page, conversationId) {
  await page.goto(`${WEB}/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
}
async function openShare(page, copy) {
  await page.getByRole("button", { name: copy.selection.title, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: copy.selection.title, exact: true });
  await dialog.getByRole("checkbox").first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(500);
  return dialog;
}
const browser = await chromium.launch();
const report = { candidates: {}, publication: null, public: [] };

async function shareScreen(conversationId, tag, language) {
  const copy = copyFor(language);
  const out = [];
  for (const [width, height] of [[1280, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, isMobile: width < 768, deviceScaleFactor: 2 });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));
    await openChat(page, conversationId);
    await page.screenshot({ path: `${OUT}/${tag}-answer-${width}-${language}.png` });
    const dialog = await openShare(page, copy);
    await page.screenshot({ path: `${OUT}/${tag}-share-${width}-${language}.png` });
    const checkbox = dialog.getByRole("checkbox").first();
    out.push({ width, language, checkboxDisabled: await checkbox.isDisabled(), dialogText: await dialog.innerText(), errors });
    await context.close();
  }
  return out;
}

async function publish(conversationId, tag, language) {
  const copy = copyFor(language);
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await openChat(page, conversationId);
  const dialog = await openShare(page, copy);
  await dialog.getByRole("checkbox").first().check();
  await page.waitForTimeout(300);
  const dialogText = await dialog.innerText();
  await page.screenshot({ path: `${OUT}/${tag}-selected-1280-${language}.png` });
  const previewResponse = page.waitForResponse((response) => response.url().endsWith("/public-excerpt-preview") && response.request().method() === "POST");
  await dialog.getByRole("button", { name: copy.selection.preview, exact: true }).click();
  const preview = await previewResponse;
  await dialog.locator("main").waitFor({ timeout: 20000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/${tag}-preview-1280-${language}.png` });
  const previewText = await dialog.locator("main").innerText();
  const createResponse = page.waitForResponse((response) => response.url().endsWith("/public-excerpt") && response.request().method() === "POST");
  const create = dialog.getByRole("button", { name: copy.owner.create, exact: true });
  if (await create.count()) await create.click();
  else await dialog.getByRole("button", { name: copy.selection.reuse, exact: true }).click();
  const created = await createResponse;
  const link = dialog.getByRole("textbox", { name: copy.owner.copy, exact: true });
  await link.waitFor({ timeout: 20000 });
  const url = await link.inputValue();
  await page.screenshot({ path: `${OUT}/${tag}-created-1280-${language}.png` });
  await context.close();
  return { dialogText, previewStatus: preview.status(), createStatus: created.status(), previewText, url, errors };
}

async function publicPage(url, tag) {
  const records = [];
  for (const [width, height] of [[1280, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, isMobile: width < 768, deviceScaleFactor: 2 });
    const page = await context.newPage();
    await context.clearCookies();
    const response = await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/${tag}-public-${width}-en.png`, fullPage: true });
    records.push({
      width,
      status: response.status(),
      cookies: await context.cookies(),
      robots: await page.evaluate(() => document.querySelector('meta[name="robots"]')?.content ?? null),
      text: await page.locator("body").innerText(),
      links: await page.evaluate(() => [...document.querySelectorAll("a[href]")].map((node) => ({ text: node.textContent.trim(), href: node.getAttribute("href") }))),
    });
    await context.close();
  }
  return records;
}

await setLanguage("en");
report.candidates.nike = await shareScreen(NIKE, "nike", "en");
report.publication = await publish(NVDA, "nvda", "en");
report.public = await publicPage(report.publication.url, "nvda");
await setLanguage("es-419");
report.candidates.appleEs = await shareScreen(APPLE_ES, "apple-es", "es-419");
await setLanguage("en");
await browser.close();
writeFileSync(`${OUT}/report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify({
  nike: report.candidates.nike.map((r) => ({ width: r.width, disabled: r.checkboxDisabled, reason: r.dialogText.split("\n").filter((line) => /source|fuente/i.test(line)) })),
  appleEs: report.candidates.appleEs.map((r) => ({ width: r.width, disabled: r.checkboxDisabled, reason: r.dialogText.split("\n").filter((line) => /fuente|source/i.test(line)) })),
  publication: { counter: report.publication.dialogText.split("\n").filter((line) => /selected|seleccionados/.test(line)), previewStatus: report.publication.previewStatus, createStatus: report.publication.createStatus, url: report.publication.url, errors: report.publication.errors },
  public: report.public.map((r) => ({ width: r.width, status: r.status, cookies: r.cookies.length, robots: r.robots, hasPrice: r.text.includes("223.67"), sourceLinks: r.links.filter((l) => /^https?:\/\//.test(l.href)).map((l) => l.href) })),
}, null, 2));
