// Local evidence driver: the five section 2 shapes, organic typed questions.
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const LANG = process.env.RAIL_LANG || "en";
const OUT = process.env.RAIL_OUT || "/tmp/shape-frames";
const BASE = "http://localhost:3100";
const API = "http://127.0.0.1:8000/api/v1";
mkdirSync(OUT, { recursive: true });
const suffix = LANG === "es-419" ? "es" : "en";

const QUESTIONS = {
  en: [
    ["20-market-pulse", "What are the biggest movers today?"],
    ["21-screening", "Show me semiconductor stocks under a 20 P/E"],
    ["22-sector-radar", "What's happening in cybersecurity stocks?"],
    ["23-comparison-p1", "Compare PLTR to LMT"],
    ["24-single-stock", "How is Netflix doing?"],
  ],
  "es-419": [
    ["20-market-pulse", "¿Cuáles son las acciones que más se mueven hoy?"],
    ["21-screening", "Muéstrame acciones de semiconductores con un P/E menor a 20"],
    ["22-sector-radar", "¿Qué está pasando en el sector de ciberseguridad?"],
    ["23-comparison-p1", "Compara PLTR con LMT"],
    ["24-single-stock", "¿Cómo le está yendo a Netflix?"],
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
    await shot(page, name);
  }

  await browser.close();
  console.log("done");
};

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
