/**
 * Evidence capture for the master-editing lane (§6 acceptance).
 *
 * Drives the real chat runtime (live interpretation) against the lane backend
 * on 8002 and the lane web server on 3002, saving frames plus the rendered
 * text of every frame to docs/reports/evidence/master-editing/. Each flow runs
 * in a fresh conversation. Run: bunx tsx e2e/support/master-editing-evidence.ts
 */

import { chromium, type Browser, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "fs";
import { join } from "path";

const WEB = "http://localhost:3002";
const API = "http://127.0.0.1:8002/api/v1";
const OUT = join(__dirname, "../../../docs/reports/evidence/master-editing");
const TEXTS: Record<string, string> = {};

async function apiPatchLanguage(language: "en" | "es-419") {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status}`);
}

async function capture(page: Page, name: string) {
  await page.waitForTimeout(400);
  const text = await page.evaluate(
    () => document.querySelector("main")?.textContent ?? "",
  );
  TEXTS[name] = text.replace(/\s+/g, " ").trim();
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false });
  console.log(`captured ${name}`);
}

async function openFreshChat(page: Page) {
  await page.goto(`${WEB}/chat`);
  await page.waitForSelector("[data-testid], textarea, [contenteditable]", {
    timeout: 30000,
  });
  await page.waitForTimeout(1200);
  // A fresh conversation: the composer on /chat with no active thread starts one.
}

async function send(page: Page, message: string) {
  const composer = page.locator('[role="combobox"], textarea').first();
  await composer.click();
  await composer.fill(message);
  await page.locator('button[type="submit"]').first().click();
}

async function waitForActiveCard(page: Page, timeoutMs = 90000) {
  await page.waitForSelector(
    'section:has([data-confirmation-status]) button:has-text("Run backtest"), section:has([data-confirmation-status]) button:has-text("Ejecutar backtest")',
    { timeout: timeoutMs },
  );
  await page.waitForTimeout(600);
}

function lastCard(page: Page) {
  return page.locator("section:has([data-confirmation-status])").last();
}

async function flowCardAndDrawers(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "Buy and hold NFLX with $10,000 through 2023"
      : "Compra y mantén NFLX con $10,000 durante 2023",
  );
  await waitForActiveCard(page);
  await capture(page, `${lang}-01-card-three-actions`);

  // Capital drawer: open, retype, apply; the superseding card carries $25,000.
  await lastCard(page).getByTestId("edit-capital").click();
  await page.waitForTimeout(400);
  await capture(page, `${lang}-02-capital-drawer-open`);
  await page.getByTestId("direct-edit-capital-input").last().fill("25000");
  await page.getByTestId("direct-edit-apply").last().click();
  await page.waitForTimeout(1500);
  await capture(page, `${lang}-03-capital-drawer-applied`);

  // Dates drawer on the superseding card.
  await lastCard(page).getByTestId("edit-dates").click();
  await page.waitForTimeout(400);
  await page.getByTestId("direct-edit-start-input").last().fill("2023-02-01");
  await page.getByTestId("direct-edit-end-input").last().fill("2023-05-31");
  await capture(page, `${lang}-04-dates-drawer-open`);
  await page.getByTestId("direct-edit-apply").last().click();
  await page.waitForTimeout(1500);
  await capture(page, `${lang}-05-dates-drawer-applied`);
}

async function flowConversationalTwin(page: Page, lang: "en" | "es") {
  // The equivalent conversational edit produces the same canonical values the
  // drawer produced (hash equality is proven in the backend suite).
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "Buy and hold NFLX with $10,000 through 2023"
      : "Compra y mantén NFLX con $10,000 durante 2023",
  );
  await waitForActiveCard(page);
  await send(
    page,
    lang === "en"
      ? "Change the starting capital to $25,000"
      : "Cambia el capital inicial a $25,000",
  );
  await waitForActiveCard(page);
  await page.waitForTimeout(1200);
  await capture(page, `${lang}-06-conversational-capital-twin`);
}

async function flowCompoundApplied(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "Buy and hold NFLX with $10,000 through 2023"
      : "Compra y mantén NFLX con $10,000 durante 2023",
  );
  await waitForActiveCard(page);
  const adjust = lang === "en" ? "Change assumptions" : "Cambiar supuestos";
  await lastCard(page).getByRole("button", { name: adjust }).click();
  await page.waitForTimeout(2500);
  await send(
    page,
    lang === "en"
      ? "Use 2024 instead, add MSFT, and make it $5,000"
      : "Usa 2024, agrega MSFT y hazlo con $5,000",
  );
  await waitForActiveCard(page);
  await page.waitForTimeout(800);
  await capture(page, `${lang}-07-compound-all-applied`);
}

async function flowCompoundUnapplied(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "Buy and hold NFLX with $10,000 through 2023"
      : "Compra y mantén NFLX con $10,000 durante 2023",
  );
  await waitForActiveCard(page);
  const adjust = lang === "en" ? "Change assumptions" : "Cambiar supuestos";
  await lastCard(page).getByRole("button", { name: adjust }).click();
  await page.waitForTimeout(2500);
  await send(
    page,
    lang === "en"
      ? "Make it $9,000 and remove TSLA from the test"
      : "Hazlo con $9,000 y quita TSLA de la prueba",
  );
  await waitForActiveCard(page);
  await page.waitForTimeout(800);
  await capture(page, `${lang}-08-compound-unapplied-disclosed`);
}

async function flowFractionalDates(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "Test AAPL for the last 8.5 months with $10,000"
      : "Prueba AAPL con los últimos 8,5 meses y $10,000",
  );
  await waitForActiveCard(page);
  await capture(page, `${lang}-09-fractional-duration-card`);
}

async function mobileDrawerSheet(browser: Browser) {
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    hasTouch: true,
    isMobile: true,
  });
  const page = await context.newPage();
  await openFreshChat(page);
  await send(page, "Buy and hold NFLX with $10,000 through 2023");
  await waitForActiveCard(page);
  await capture(page, "en-10-mobile-card");
  await lastCard(page).getByTestId("edit-capital").click();
  await page.waitForTimeout(900);
  await capture(page, "en-11-mobile-capital-sheet");
  await page.getByTestId("direct-edit-capital-input").last().fill("25000");
  await page.getByTestId("direct-edit-apply").last().click();
  await page.waitForTimeout(1800);
  await capture(page, "en-12-mobile-capital-applied");
  await context.close();
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  await apiPatchLanguage("en");
  await flowCardAndDrawers(page, "en");
  await flowConversationalTwin(page, "en");
  await flowCompoundApplied(page, "en");
  await flowCompoundUnapplied(page, "en");
  await flowFractionalDates(page, "en");

  await apiPatchLanguage("es-419");
  await page.reload();
  await flowCardAndDrawers(page, "es");
  await flowCompoundApplied(page, "es");
  await flowCompoundUnapplied(page, "es");
  await flowFractionalDates(page, "es");

  await apiPatchLanguage("en");
  await mobileDrawerSheet(browser);

  writeFileSync(
    join(OUT, "rendered-text.json"),
    JSON.stringify(TEXTS, null, 2) + "\n",
  );
  await browser.close();
  console.log("done");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
