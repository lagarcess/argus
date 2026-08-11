/** Envelope-refusal frames: an out-of-band capital and an over-cap cost are
 * refused inline with the engine's own bounds named, and the card is
 * untouched. Merges frames into the existing evidence set.
 * Run from web/: bunx tsx e2e/support/master-editing-envelope-delta.ts */

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

async function envelopeRefusals(page: Page, lang: "en" | "es") {
  await plant(page, lang);
  const before = await cards(page).count();

  await cards(page).last().getByTestId("edit-capital").click();
  await page.waitForTimeout(400);
  await page.getByTestId("direct-edit-capital-input").fill("50");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(800);
  await capture(page, `${lang}-12-capital-band-refused`);
  const capitalText = TEXTS[`${lang}-12-capital-band-refused`];
  const bandMarker = lang === "en" ? "between $1,000" : "entre $1,000";
  if (!capitalText.includes(bandMarker)) {
    throw new Error(`${lang}-12: band refusal not rendered`);
  }
  if (!capitalText.includes("$10,000")) {
    throw new Error(`${lang}-12: card must remain untouched`);
  }
  await page.getByTestId("direct-edit-cancel").click();
  await page.waitForTimeout(300);

  await cards(page).last().getByTestId("edit-costs").click();
  await page.waitForTimeout(400);
  await page.getByTestId("direct-edit-slippage-input").fill("9");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(800);
  await capture(page, `${lang}-13-cost-cap-refused`);
  const costText = TEXTS[`${lang}-13-cost-cap-refused`];
  if (!costText.includes("5")) {
    throw new Error(`${lang}-13: cost cap refusal not rendered`);
  }
  if ((await cards(page).count()) !== before) {
    throw new Error(`${lang}: a refusal must not change the transcript`);
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
  await run("en-envelope", () => envelopeRefusals(page, "en"));
  await apiPatchLanguage("es-419");
  await page.reload();
  await run("es-envelope", () => envelopeRefusals(page, "es"));
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
