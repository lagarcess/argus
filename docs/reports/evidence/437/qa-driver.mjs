// Flag-on in-place surface QA matrix for issue #437.
// Captures durable frames per (language, width) cell against the local
// flag-on stack: card with pills, capital drawer open, capital applied,
// dates drawer open, dates applied; desktop cells continue through
// cancel -> new card -> run -> result.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:3011";
const OUT = process.env.QA_OUT;
if (!OUT) throw new Error("QA_OUT is required");
mkdirSync(OUT, { recursive: true });

const ALL_CELLS = [
  {
    name: "desktop-en",
    lang: "en",
    viewport: { width: 1280, height: 800 },
    idea: "Buy and hold Apple for the last year with $10,000",
    followup: "Buy and hold Apple for the last two years with $12,000",
    labels: {
      capital: "Edit capital",
      dates: "Edit dates",
      apply: "Apply",
      send: "Send message",
      run: "Run backtest",
      cancel: "Cancel",
      complete: "Simulation Complete",
    },
    journey: true,
  },
  {
    name: "desktop-es",
    lang: "es-419",
    viewport: { width: 1280, height: 800 },
    idea: "Comprar y mantener Apple durante el ultimo anio con $10,000",
    followup: "Comprar y mantener Apple durante los ultimos dos anios con $12,000",
    labels: {
      capital: "Editar capital",
      dates: "Editar fechas",
      apply: "Aplicar",
      send: "Enviar mensaje",
      run: "Ejecutar backtest",
      cancel: "Cancelar",
      complete: "Simulación completa",
    },
    journey: true,
  },
  {
    name: "phone-en",
    lang: "en",
    viewport: { width: 375, height: 812 },
    idea: "Buy and hold Apple for the last year with $10,000",
    labels: {
      capital: "Edit capital",
      dates: "Edit dates",
      apply: "Apply",
      send: "Send message",
    },
    journey: false,
  },
  {
    name: "phone-es",
    lang: "es-419",
    viewport: { width: 375, height: 812 },
    idea: "Comprar y mantener Apple durante el ultimo anio con $10,000",
    labels: {
      capital: "Editar capital",
      dates: "Editar fechas",
      apply: "Aplicar",
      send: "Enviar mensaje",
    },
    journey: false,
  },
];

const CELLS = ALL_CELLS.filter((cell) => cell.name !== "desktop-en");

const shot = (page, cell, tag) =>
  page.screenshot({ path: `${OUT}/${cell.name}-${tag}.png`, fullPage: false });

async function sendMessage(page, cell, text) {
  const composer = page.getByRole("combobox").first();
  await composer.click();
  await page.keyboard.type(text, { delay: 8 });
  await page.getByRole("button", { name: cell.labels.send }).click();
}

async function waitForPill(page, cell) {
  await page
    .getByRole("button", { name: cell.labels.capital })
    .last()
    .waitFor({ state: "visible", timeout: 120_000 });
}

async function run() {
  const browser = await chromium.launch();
  for (const cell of CELLS) {
    const context = await browser.newContext({ viewport: cell.viewport });
    await context.addInitScript((lang) => {
      window.localStorage.setItem("i18nextLng", lang);
    }, cell.lang);
    const page = await context.newPage();
    await page.request.patch("http://127.0.0.1:8010/api/v1/me", {
      data: { language: cell.lang },
    });
    page.setDefaultTimeout(120_000);
    await page.goto(`${BASE}/chat`, { waitUntil: "networkidle" });

    await shot(page, cell, "0-loaded");
    await sendMessage(page, cell, cell.idea);
    await waitForPill(page, cell);
    await page.waitForTimeout(600);
    await shot(page, cell, "1-card");

    // Capital drawer: open, retype the amount, frame, apply.
    await page.getByRole("button", { name: cell.labels.capital }).last().click();
    const capitalInput = page.locator('input[type="text"]').last();
    await capitalInput.waitFor({ state: "visible" });
    await capitalInput.fill("25000");
    await shot(page, cell, "2-capital-drawer");
    await page.getByRole("button", { name: cell.labels.apply }).last().click();
    await page.waitForTimeout(1500);
    await shot(page, cell, "3-capital-applied");

    // Dates drawer: open, move the start date, frame, apply.
    await page.getByRole("button", { name: cell.labels.dates }).last().click();
    const startInput = page.locator('input[type="date"]').first();
    await startInput.waitFor({ state: "visible" });
    await startInput.fill("2024-08-11");
    await shot(page, cell, "4-dates-drawer");
    await page.getByRole("button", { name: cell.labels.apply }).last().click();
    await page.waitForTimeout(1500);
    await shot(page, cell, "5-dates-applied");

    if (cell.journey) {
      // Cancel the draft, ask again, run the new card to a result.
      await page.getByRole("button", { name: cell.labels.cancel }).last().click();
      await page.waitForTimeout(2500);
      await shot(page, cell, "6-cancelled");
      await sendMessage(page, cell, cell.followup);
      await waitForPill(page, cell);
      await page.waitForTimeout(600);
      await shot(page, cell, "7-new-card");
      await page.getByRole("button", { name: cell.labels.run }).last().click();
      await page
        .getByText(cell.labels.complete)
        .last()
        .waitFor({ state: "visible", timeout: 180_000 });
      await page.waitForTimeout(1200);
      await shot(page, cell, "8-result");
    }

    await context.close();
    console.log(`cell done: ${cell.name}`);
  }
  await browser.close();
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
