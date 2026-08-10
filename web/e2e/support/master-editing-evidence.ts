/**
 * Browser evidence for the master-editing lane, five-findings revision:
 * ExecutionDetails pills host in-place capital/dates/costs editing, an
 * in-place edit updates the same card and mints nothing, actions share the
 * card's content margin, compound disclosure still rides the card, and
 * researched peer rows add to a pending card without a turn.
 *
 * Run from web/: bunx tsx e2e/support/master-editing-evidence.ts
 * Requires the lane backend on 8002 with real providers and
 * ARGUS_RESEARCH_RAIL_ENABLED=true, and lane web on 3002.
 */

import { chromium, type Browser, type Page } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";

const WEB = "http://localhost:3002";
const API = "http://127.0.0.1:8002/api/v1";
const OUT = join(__dirname, "../../../docs/reports/evidence/master-editing");
const TEXTS: Record<string, string> = existsSync(join(OUT, "rendered-text.json"))
  ? JSON.parse(readFileSync(join(OUT, "rendered-text.json"), "utf-8"))
  : {};
// EVIDENCE_FLOWS=en-peers,es-disclosure re-runs a subset into the same set.
const ONLY = new Set(
  (process.env.EVIDENCE_FLOWS ?? "").split(",").filter(Boolean),
);

async function apiPatchLanguage(language: "en" | "es-419") {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status}`);
}

async function capture(page: Page, name: string) {
  await page.waitForTimeout(600);
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

async function waitForCards(page: Page, count: number, timeoutMs = 180000) {
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

async function openFreshChat(page: Page) {
  await page.goto(`${WEB}/chat`);
  await page.waitForSelector('[role="combobox"], textarea', { timeout: 30000 });
  await page.waitForTimeout(1200);
}

async function waitForComposerEnabled(page: Page, timeoutMs = 240000) {
  // A background research job keeps the conversation busy after the answer
  // text settles; the composer's disabled state is the honest signal.
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="chat-input"]');
      return el !== null && el.getAttribute("aria-disabled") !== "true";
    },
    undefined,
    { timeout: timeoutMs },
  );
}

async function send(page: Page, message: string) {
  await waitForComposerEnabled(page);
  const composer = page.locator('[role="combobox"], textarea').first();
  await composer.click();
  await composer.fill(message);
  await page.locator('button[type="submit"]').first().click();
}

async function waitForAssistantSettled(page: Page, timeoutMs = 180000) {
  const started = Date.now();
  let last = "";
  let stable = 0;
  while (Date.now() - started < timeoutMs) {
    const text = await page.evaluate(
      () => document.querySelector("main")?.textContent ?? "",
    );
    if (text === last && !text.includes("Thinking")) {
      stable += 1;
      if (stable >= 3) return;
    } else {
      stable = 0;
    }
    last = text;
    await page.waitForTimeout(1500);
  }
}

/** The card must survive its own drawer: header, money row, period,
 * assumptions, and actions all still rendered while the drawer is open. */
async function assertCardSurvives(page: Page, lang: "en" | "es", when: string) {
  const text = (
    await page.evaluate(() => document.querySelector("main")?.textContent ?? "")
  ).replace(/\s+/g, " ");
  const run = lang === "en" ? "Run backtest" : "Ejecutar backtest";
  const period = "2023";
  const money = "$";
  for (const needle of ["NFLX", money, period, run]) {
    if (!text.includes(needle)) {
      throw new Error(`${lang} ${when}: card content "${needle}" missing while drawer open`);
    }
  }
}

const IDEA = {
  en: "Buy and hold NFLX with $10,000 through 2023",
  es: "Compra y mant\u00e9n NFLX con $10,000 durante 2023",
};

async function plantCard(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(page, IDEA[lang]);
  await waitForCards(page, 1);
}

/** Findings 1, 2, 3, 4: pills, one in-place behaviour, no minting, margins. */
async function inPlaceEditing(page: Page, lang: "en" | "es") {
  await plantCard(page, lang);
  await capture(page, `${lang}-01-card-pills-and-actions`);
  const before = await cards(page).count();

  await cards(page).last().getByTestId("edit-capital").click();
  await page.waitForTimeout(400);
  await assertCardSurvives(page, lang, "capital drawer");
  await capture(page, `${lang}-02-capital-panel-open`);
  await page.getByTestId("direct-edit-capital-input").fill("25000");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(2500);
  if ((await cards(page).count()) !== before) {
    throw new Error(`${lang}: capital edit minted a card`);
  }
  await capture(page, `${lang}-03-capital-applied-in-place`);
  const capitalText = TEXTS[`${lang}-03-capital-applied-in-place`];
  if (!capitalText.includes("$25,000")) {
    throw new Error(`${lang}: edited capital not rendered`);
  }

  await cards(page).last().getByTestId("edit-dates").click();
  await page.waitForTimeout(400);
  await assertCardSurvives(page, lang, "dates drawer");
  await capture(page, `${lang}-04-dates-panel-open`);
  await page.getByTestId("direct-edit-start-input").fill("2023-02-01");
  await page.getByTestId("direct-edit-end-input").fill("2023-05-31");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(2500);
  if ((await cards(page).count()) !== before) {
    throw new Error(`${lang}: date edit minted a card`);
  }
  await capture(page, `${lang}-05-dates-applied-in-place`);

  await cards(page).last().getByTestId("edit-costs").click();
  await page.waitForTimeout(400);
  await assertCardSurvives(page, lang, "costs drawer");
  await capture(page, `${lang}-06-costs-panel-open`);
  await page.getByTestId("direct-edit-fee-input").fill("0.2");
  await page.getByTestId("direct-edit-slippage-input").fill("0.1");
  await page.getByTestId("direct-edit-apply").click();
  await page.waitForTimeout(2500);
  if ((await cards(page).count()) !== before) {
    throw new Error(`${lang}: cost edit minted a card`);
  }
  await capture(page, `${lang}-07-costs-applied-in-place`);
  const costText = TEXTS[`${lang}-07-costs-applied-in-place`];
  if (!/20\s?bps|0\.2\s?%|0,2\s?%/.test(costText)) {
    throw new Error(`${lang}: edited costs not rendered`);
  }
}

/** \u00a73.2 compound disclosure still rides the card after the rework. */
async function compoundDisclosure(page: Page, lang: "en" | "es") {
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
  await waitForCards(page, before + 1);
  await capture(page, `${lang}-08-compound-unapplied-disclosed`);
  const text = TEXTS[`${lang}-08-compound-unapplied-disclosed`];
  if (!text.includes("could not change") && !text.includes("No pude cambiar")) {
    throw new Error(`${lang}-08: no disclosure line rendered`);
  }
}

/** Finding 5: researched peer rows on a pending card, add without a turn. */
async function peerRows(page: Page, lang: "en" | "es") {
  await openFreshChat(page);
  await send(
    page,
    lang === "en"
      ? "What is happening in streaming stocks?"
      : "\u00bfQu\u00e9 est\u00e1 pasando con las acciones de streaming?",
  );
  await waitForAssistantSettled(page);
  await waitForComposerEnabled(page);
  await page.waitForTimeout(1500);
  await send(page, IDEA[lang]);
  await waitForCards(page, 1);
  await page.waitForTimeout(1500);
  await capture(page, `${lang}-10-peer-rows-on-card`);
  const rowsText = TEXTS[`${lang}-10-peer-rows-on-card`];
  const marker = lang === "en" ? "to this test" : "a esta prueba";
  if (!rowsText.includes(marker)) {
    throw new Error(`${lang}-10: no peer row rendered`);
  }
  const cardsBefore = await cards(page).count();
  const addRow = page.locator(`button:has-text("${marker}")`).first();
  await addRow.click();
  await page.waitForTimeout(3500);
  if ((await cards(page).count()) !== cardsBefore) {
    throw new Error(`${lang}: peer add minted a card; non-turn changes never do`);
  }
  await capture(page, `${lang}-11-peer-added-without-turn`);
}

/** Mobile width: the same in-flow drawer; the card survives it here too. */
async function mobile(browser: Browser, lang: "en" | "es") {
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
  });
  const page = await context.newPage();
  await plantCard(page, lang);
  await capture(page, `${lang}-09-mobile-card`);
  const before = await cards(page).count();
  await cards(page).last().getByTestId("edit-capital").click();
  await page.waitForTimeout(700);
  await assertCardSurvives(page, lang, "mobile capital drawer");
  await capture(page, `${lang}-09b-mobile-capital-drawer`);
  await cards(page).last().getByTestId("edit-costs").click();
  await page.waitForTimeout(700);
  await assertCardSurvives(page, lang, "mobile costs drawer");
  await capture(page, `${lang}-09c-mobile-costs-drawer`);
  if ((await cards(page).count()) !== before) {
    throw new Error(`${lang}: mobile drawer changed the card count`);
  }
  await context.close();
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
  const failures: string[] = [];
  async function run(name: string, flow: () => Promise<void>) {
    if (ONLY.size > 0 && !ONLY.has(name)) return;
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
  await run("en-editing", () => inPlaceEditing(page, "en"));
  await run("en-disclosure", () => compoundDisclosure(page, "en"));
  await run("en-peers", () => peerRows(page, "en"));
  await run("en-mobile", () => mobile(browser, "en"));

  await apiPatchLanguage("es-419");
  await page.reload();
  await run("es-editing", () => inPlaceEditing(page, "es"));
  await run("es-disclosure", () => compoundDisclosure(page, "es"));
  await run("es-peers", () => peerRows(page, "es"));
  await run("es-mobile", () => mobile(browser, "es"));
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
