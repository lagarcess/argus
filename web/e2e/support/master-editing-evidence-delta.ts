/**
 * Delta re-captures for four frames: waits on card-count increase, and the
 * unapplied-disclosure flow uses a deterministically rejected change (slippage
 * above the 5% cap) so the typed disclosure cannot depend on model mood.
 * Run from web/: bunx tsx e2e/support/master-editing-evidence-delta.ts
 */

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

async function waitForMoreCards(page: Page, than: number, timeoutMs = 150000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if ((await cards(page).count()) > than) {
      await page.waitForTimeout(900);
      return;
    }
    await page.waitForTimeout(1200);
  }
  throw new Error(`no new card appeared beyond ${than}`);
}

async function openFreshChat(page: Page) {
  await page.goto(`${WEB}/chat`);
  await page.waitForSelector('[role="combobox"], textarea', { timeout: 30000 });
  await page.waitForTimeout(1200);
}

async function send(page: Page, message: string) {
  const composer = page.locator('[role="combobox"], textarea').first();
  await composer.click();
  await composer.fill(message);
  await page.locator('button[type="submit"]').first().click();
}

async function plantCard(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "Buy and hold NFLX with $10,000 through 2023"
      : "Compra y mantén NFLX con $10,000 durante 2023",
  );
  await waitForMoreCards(page, 0);
}

async function datesApplied(page: Page) {
  await plantCard(page, "en");
  const before = await cards(page).count();
  await cards(page).last().getByTestId("edit-dates").click();
  await page.waitForTimeout(400);
  await page.getByTestId("direct-edit-start-input").last().fill("2023-02-01");
  await page.getByTestId("direct-edit-end-input").last().fill("2023-05-31");
  await page.getByTestId("direct-edit-apply").last().click();
  await waitForMoreCards(page, before);
  await capture(page, "en-05-dates-drawer-applied");
}

async function conversationalTwin(page: Page) {
  await plantCard(page, "en");
  const before = await cards(page).count();
  await send(page, "Change the starting capital to $25,000");
  await waitForMoreCards(page, before);
  await capture(page, "en-06-conversational-capital-twin");
}

async function unappliedDisclosed(page: Page, lang: "en" | "es") {
  await plantCard(page, lang);
  const adjust = lang === "en" ? "Change assumptions" : "Cambiar supuestos";
  await cards(page).last().getByRole("button", { name: adjust }).click();
  await page.waitForTimeout(2500);
  const before = await cards(page).count();
  await send(
    page,
    lang === "en"
      ? "Make it $9,000 and set slippage to 90%"
      : "Hazlo con $9,000 y pon el deslizamiento en 90%",
  );
  await waitForMoreCards(page, before);
  await capture(page, `${lang}-08-compound-unapplied-disclosed`);
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
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
  await run("en-05", () => datesApplied(page));
  await run("en-06", () => conversationalTwin(page));
  await run("en-08", () => unappliedDisclosed(page, "en"));
  await apiPatchLanguage("es-419");
  await page.reload();
  await run("es-08", () => unappliedDisclosed(page, "es"));
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
