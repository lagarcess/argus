// Local-only Playwright drive for the publisher honesty lane (#579, #580).
// Loads the conversations replay_api.py seeded with the clock frozen after the
// New York close, sets the profile language through the API, and records what
// the S&P week answer's sources drawer and the zero-retrieval answer say, at
// desktop and phone widths. Run with node after `bun install` in web/; no
// provider is touched.
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const TREE = process.env.PH_QA_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const SEED = JSON.parse(readFileSync(process.env.PH_QA_IDS_FILE, "utf-8"));
const OUT = `${TREE}/docs/reports/evidence/publisher-honesty/browser`;
mkdirSync(OUT, { recursive: true });
const API = `http://127.0.0.1:${process.env.PH_QA_API_PORT ?? "8591"}/api/v1`;
const WEB = `http://127.0.0.1:${process.env.PH_QA_WEB_PORT ?? "3591"}`;

const COPY = {
  en: {
    sourcesTitle: "Sources Argus read",
    withheldTitle: "Where Argus looked",
    notGrounded: "I couldn't retrieve the data to answer this question.",
  },
  "es-419": {
    sourcesTitle: "Fuentes que Argus consultó",
    withheldTitle: "Dónde buscó Argus",
    notGrounded: "No pude recuperar los datos para responder esta pregunta.",
  },
};
const SPX_FIGURE = "82.24";
const SPX_DOMAINS = ["lasvegassun.com", "thestockmarketwatch.com"];
// The recorded zero-tool response's own prose, which must not reach the reader.
const MODEL_PROSE = "retrieve live market data right now";

async function setLanguage(language) {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status} ${await response.text()}`);
}

const browser = await chromium.launch();
const report = { seed: SEED.meta, turns: [] };
for (const language of ["en", "es-419"]) {
  await setLanguage(language);
  const copy = COPY[language];
  for (const [width, height] of [[1280, 900], [390, 844]]) {
    const context = await browser.newContext({
      viewport: { width, height },
      isMobile: width < 768,
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));

    await page.goto(`${WEB}/chat?conversation=${SEED.conversations[language].spx}`, {
      waitUntil: "networkidle",
    });
    await page.getByText(SPX_FIGURE, { exact: false }).first().waitFor({ timeout: 30000 });
    const open = page.getByTestId("research-sources-open");
    await open.waitFor({ timeout: 15000 });
    const buttonText = (await open.innerText()).trim();
    await page.screenshot({ path: `${OUT}/spx-week-answer-${width}-${language}.png` });
    await open.click();
    await page.getByText(copy.sourcesTitle, { exact: true }).first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(600);
    const drawerText = await page.locator("body").innerText();
    await page.screenshot({ path: `${OUT}/spx-week-sources-${width}-${language}.png` });
    report.turns.push({
      turn: "spx-week",
      language,
      width,
      buttonText,
      drawerTitle: copy.sourcesTitle,
      domainsListed: SPX_DOMAINS.filter((domain) => drawerText.includes(domain)),
      framedAsWhereArgusLooked: drawerText.includes(copy.withheldTitle),
      pageErrors: [...errors],
    });

    errors.length = 0;
    await page.goto(
      `${WEB}/chat?conversation=${SEED.conversations[language].not_grounded}`,
      { waitUntil: "networkidle" },
    );
    await page.getByText(copy.notGrounded, { exact: true }).first().waitFor({ timeout: 30000 });
    await page.waitForTimeout(600);
    const bodyText = await page.locator("body").innerText();
    await page.screenshot({ path: `${OUT}/not-grounded-${width}-${language}.png` });
    report.turns.push({
      turn: "not-grounded",
      language,
      width,
      noteShown: bodyText.includes(copy.notGrounded),
      modelProseShown: bodyText.includes(MODEL_PROSE),
      sourcesButtons: await page.getByTestId("research-sources-open").count(),
      pageErrors: [...errors],
    });
    await context.close();
  }
}
await browser.close();
writeFileSync(`${OUT}/report.json`, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
