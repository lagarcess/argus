// Local evidence: sources through the typed panel, and a recent-IPO row.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const LANG = process.env.RAIL_LANG || "en";
const OUT = process.env.RAIL_OUT || "/tmp/followup-frames";
const BASE = "http://localhost:3100";
const API = "http://127.0.0.1:8000/api/v1";
mkdirSync(OUT, { recursive: true });
const suffix = LANG === "es-419" ? "es" : "en";

const QUESTIONS = {
  en: [
    ["30-sector-radar-sources", "What's happening in cybersecurity stocks?"],
    ["31-market-pulse-sources", "What are the biggest movers today?"],
    ["32-recent-ipo-window", "How is Swarmer SWMR doing?"],
  ],
  "es-419": [
    ["30-sector-radar-sources", "¿Qué está pasando en el sector de ciberseguridad?"],
    ["31-market-pulse-sources", "¿Cuáles son las acciones que más se mueven hoy?"],
    ["32-recent-ipo-window", "¿Cómo le está yendo a Swarmer SWMR?"],
  ],
};

async function shot(page, name) {
  await page.screenshot({ path: join(OUT, `${name}-${suffix}.png`) });
  writeFileSync(
    join(OUT, `${name}-${suffix}.txt`),
    await page.evaluate(() => document.body.innerText),
  );
  console.log(`[shot] ${name}-${suffix}`);
}

async function waitTurn(page, timeout = 300000) {
  await page.waitForTimeout(2500);
  await page.waitForFunction(
    () =>
      !/is working on|está trabajando|Understanding your idea|Entendiendo tu idea/.test(
        document.body.innerText,
      ),
    undefined,
    { timeout },
  );
  await page.waitForTimeout(3000);
}

const run = async () => {
  const browser = await chromium.launch();
  const page = await (
    await browser.newContext({ viewport: { width: 1280, height: 900 } })
  ).newPage();
  await page.request.patch(`${API}/me`, { data: { language: LANG } });

  for (const [name, question] of QUESTIONS[LANG]) {
    await page.goto(BASE, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-testid="chat-input"]', { timeout: 30000 });
    await page.waitForTimeout(1200);
    await page.locator('[data-testid="chat-input"]').click();
    await page.keyboard.type(question, { delay: 8 });
    await page.keyboard.press("Enter");
    await waitTurn(page);
    // Open the typed sources panel when the answer carries sources.
    const sourcesButton = page.locator('[data-testid="research-sources-open"]');
    if (await sourcesButton.count()) {
      await sourcesButton.first().click();
      await page.waitForTimeout(1200);
      await shot(page, `${name}-panel`);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(600);
    }
    await shot(page, name);
  }

  await browser.close();
  console.log("done");
};

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
