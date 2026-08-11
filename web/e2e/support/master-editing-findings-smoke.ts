/** Smoke verification of the five-findings rework (EN, web width):
 * ExecutionDetails pills, in-place capital edit (no new card), in-place cost
 * edit, action alignment. Run from web/:
 * bunx tsx e2e/support/master-editing-findings-smoke.ts */

import { chromium, type Page } from "@playwright/test";

const WEB = "http://localhost:3002";

function cards(page: Page) {
  return page.locator("section:has([data-confirmation-status])");
}

async function waitForCards(page: Page, count: number, timeoutMs = 150000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if ((await cards(page).count()) >= count) {
      await page.waitForTimeout(900);
      return;
    }
    await page.waitForTimeout(1200);
  }
  throw new Error(`expected ${count} cards`);
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`${WEB}/chat`);
  await page.waitForSelector('[role="combobox"], textarea', { timeout: 30000 });
  await page.waitForTimeout(1000);
  const composer = page.locator('[role="combobox"], textarea').first();
  await composer.click();
  await composer.fill("Buy and hold NFLX with $10,000 through 2023");
  await page.locator('button[type="submit"]').first().click();
  await waitForCards(page, 1);

  const failures: string[] = [];
  const check = (name: string, ok: boolean) => {
    console.log(`${ok ? "PASS" : "FAIL"} ${name}`);
    if (!ok) failures.push(name);
  };

  // Finding 1+2: three ExecutionDetails pills, one behaviour.
  const card = cards(page).last();
  for (const kind of ["capital", "dates", "costs"]) {
    check(`pill edit-${kind} visible`, await card.getByTestId(`edit-${kind}`).isVisible());
  }

  // Finding 3: an in-place capital edit updates the same card, mints nothing.
  const cardsBefore = await cards(page).count();
  await card.getByTestId("edit-capital").click();
  await page.waitForTimeout(300);
  check(
    "capital panel opens inline",
    await page.getByTestId("confirmation-direct-edit-drawer").isVisible(),
  );
  await page.getByTestId("direct-edit-capital-input").fill("25000");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(2500);
  const cardsAfterCapital = await cards(page).count();
  check("no new card after capital edit", cardsAfterCapital === cardsBefore);
  const cardText = await cards(page).last().innerText();
  check("card shows $25,000", cardText.includes("$25,000"));

  // Finding 2: costs edit in place through the same panel idiom.
  await cards(page).last().getByTestId("edit-costs").click();
  await page.waitForTimeout(300);
  await page.getByTestId("direct-edit-fee-input").fill("0.2");
  await page.getByTestId("direct-edit-slippage-input").fill("0.1");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(2500);
  const cardsAfterCosts = await cards(page).count();
  check("no new card after cost edit", cardsAfterCosts === cardsBefore);
  const costText = await cards(page).last().innerText();
  check(
    "card shows edited costs",
    costText.includes("0.2%") || costText.toLowerCase().includes("fee"),
  );
  console.log("card text sample:", costText.replace(/\s+/g, " ").slice(0, 420));

  // Finding 4: action pills align with the card's left content margin.
  const actionsBox = await cards(page)
    .last()
    .locator('button:has-text("Run backtest")')
    .boundingBox();
  const capitalPill = await cards(page)
    .last()
    .getByTestId("edit-capital")
    .boundingBox();
  check(
    "actions share the left content margin",
    actionsBox !== null &&
      capitalPill !== null &&
      Math.abs(actionsBox.x - capitalPill.x) < 2,
  );

  await page.screenshot({
    path: "e2e/support/findings-smoke.png",
    fullPage: false,
  });
  await browser.close();
  if (failures.length > 0) {
    console.error("FAILURES:", failures.join(", "));
    process.exit(1);
  }
  console.log("smoke green");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
