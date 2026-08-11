/** The date picker clamps to today: both inputs carry max=today in the DOM,
 * and a typed future date refuses immediately with no network round trip.
 * Merges frames into the evidence set.
 * Run from web/: bunx tsx e2e/support/master-editing-datebound-delta.ts */

import { chromium, type Page } from "@playwright/test";
import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";

const WEB = "http://localhost:3002";
const API = "http://127.0.0.1:8002/api/v1";
const OUT = join(__dirname, "../../../docs/reports/evidence/master-editing");
const TEXTS: Record<string, string> = existsSync(join(OUT, "rendered-text.json"))
  ? JSON.parse(readFileSync(join(OUT, "rendered-text.json"), "utf-8"))
  : {};

async function apiPatchLanguage(language: "en" | "es-419") {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status}`);
}

async function capture(page: Page, name: string) {
  await page.waitForTimeout(500);
  const text = await page.evaluate(
    () => document.querySelector("main")?.textContent ?? "",
  );
  TEXTS[name] = text.replace(/\s+/g, " ").trim();
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false });
  console.log(`captured ${name}`);
}

function cards(page: Page) {
  return page.locator("section:has([data-confirmation-status])");
}

async function plant(page: Page, lang: "en" | "es") {
  await page.goto(`${WEB}/chat`);
  await page.waitForSelector('[role="combobox"], textarea', { timeout: 30000 });
  await page.waitForTimeout(1200);
  const composer = page.locator('[role="combobox"], textarea').first();
  await composer.click();
  await composer.fill(
    lang === "en"
      ? "Buy and hold NFLX with $10,000 through 2023"
      : "Compra y mantén NFLX con $10,000 durante 2023",
  );
  await page.locator('button[type="submit"]').first().click();
  const started = Date.now();
  while (Date.now() - started < 180000) {
    if ((await cards(page).count()) >= 1) break;
    await page.waitForTimeout(1200);
  }
  await page.waitForTimeout(1000);
}

async function dateBound(page: Page, lang: "en" | "es") {
  await plant(page, lang);
  await cards(page).last().getByTestId("edit-dates").click();
  await page.waitForTimeout(400);

  const today = await page.evaluate(() => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
  });
  for (const testId of ["direct-edit-start-input", "direct-edit-end-input"]) {
    const max = await page.getByTestId(testId).getAttribute("max");
    if (max !== today) {
      throw new Error(`${lang} ${testId}: max=${max}, expected today ${today}`);
    }
  }
  console.log(`${lang}: both date inputs clamp to ${today}`);

  let editCalls = 0;
  page.on("request", (request) => {
    if (request.url().includes("/direct-edit")) editCalls += 1;
  });
  await page.getByTestId("direct-edit-start-input").fill("2029-01-01");
  await page.getByTestId("direct-edit-end-input").fill("2030-01-01");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(700);
  await capture(page, `${lang}-14-future-date-refused-instantly`);
  const text = TEXTS[`${lang}-14-future-date-refused-instantly`];
  const marker =
    lang === "en" ? "on or before today" : "igual o anterior a hoy";
  if (!text.includes(marker)) {
    throw new Error(`${lang}-14: instant refusal not rendered`);
  }
  if (editCalls !== 0) {
    throw new Error(`${lang}-14: refusal must not cost a round trip`);
  }
  if (!text.includes("2023")) {
    throw new Error(`${lang}-14: card must remain untouched`);
  }
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const failures: string[] = [];
  async function run(name: string, flow: () => Promise<void>) {
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      try {
        await flow();
        return;
      } catch (error) {
        console.error(`flow ${name} attempt ${attempt} failed:`, error);
      }
    }
    failures.push(name);
  }

  await apiPatchLanguage("en");
  await run("en-datebound", () => dateBound(page, "en"));
  await apiPatchLanguage("es-419");
  await page.reload();
  await run("es-datebound", () => dateBound(page, "es"));
  await apiPatchLanguage("en");

  writeFileSync(
    join(OUT, "rendered-text.json"),
    JSON.stringify(TEXTS, null, 2) + "\n",
  );
  await browser.close();
  if (failures.length > 0) {
    console.error("flows without captures:", failures.join(", "));
    process.exit(2);
  }
  console.log("done");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
