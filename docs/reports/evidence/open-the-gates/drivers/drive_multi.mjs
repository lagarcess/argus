// Six eligible turns in one conversation: Select all, the count, preview,
// create, and the public page at phone width. Proves the cap is gone in the
// browser, on the seeded copies of the lane's real NVIDIA answer.
import { createRequire } from "node:module";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";

const TREE = process.env.OTG_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const OUT = `${TREE}/docs/reports/evidence/open-the-gates/browser`;
mkdirSync(OUT, { recursive: true });
const WEB = "http://127.0.0.1:3590";
const copy = JSON.parse(readFileSync(`${TREE}/web/public/locales/en/common.json`, "utf-8")).receipt;
const { conversation_id } = JSON.parse(readFileSync(process.env.OTG_IDS_FILE, "utf-8"));

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(String(error)));
await page.goto(`${WEB}/chat?conversation=${conversation_id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.evaluate(() => document.querySelectorAll("nextjs-portal").forEach((node) => node.remove()));
await page.getByRole("button", { name: copy.selection.title, exact: true }).click();
const dialog = page.getByRole("dialog", { name: copy.selection.title, exact: true });
await dialog.getByRole("checkbox").first().waitFor({ timeout: 20000 });
const before = await dialog.innerText();
await dialog.getByRole("button", { name: copy.selection.all, exact: true }).click();
await page.waitForTimeout(400);
const checked = await dialog.locator('input[type="checkbox"]:checked').count();
const afterText = await dialog.innerText();
await page.screenshot({ path: `${OUT}/six-turns-select-all-1280-en.png` });
const previewResponse = page.waitForResponse((response) => response.url().endsWith("/public-excerpt-preview") && response.request().method() === "POST");
await dialog.getByRole("button", { name: copy.selection.preview, exact: true }).click();
const preview = await previewResponse;
await dialog.locator("main").waitFor({ timeout: 20000 });
await page.waitForTimeout(800);
await page.screenshot({ path: `${OUT}/six-turns-preview-1280-en.png` });
const createResponse = page.waitForResponse((response) => response.url().endsWith("/public-excerpt") && response.request().method() === "POST");
await dialog.getByRole("button", { name: copy.owner.create, exact: true }).click();
const created = await createResponse;
const link = dialog.getByRole("textbox", { name: copy.owner.copy, exact: true });
await link.waitFor({ timeout: 20000 });
const url = await link.inputValue();
await context.close();

const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 2 });
const publicPage = await phone.newPage();
const response = await publicPage.goto(url, { waitUntil: "networkidle" });
await publicPage.waitForTimeout(800);
await publicPage.screenshot({ path: `${OUT}/six-turns-public-390-en.png`, fullPage: true });
const text = await publicPage.locator("body").innerText();
const turns = (text.match(/NVIDIA is moving lower this week/g) || []).length;
await browser.close();
const report = { conversation_id_private: true, counterBefore: before.split("\n").filter((l) => /selected/.test(l)), counterAfter: afterText.split("\n").filter((l) => /selected/.test(l)), checked, capCopy: /up to \d+ answers/.test(afterText), previewStatus: preview.status(), createStatus: created.status(), publicStatus: response.status(), publicTurns: turns, errors };
writeFileSync(`${OUT}/six-turns-report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
