// Local-only Playwright drive for PR #568: loads the two seeded conversations
// from replay_api.py, sets the profile language through the API, opens the
// withheld turn at desktop and mobile widths, and records what the surface
// says. Run with node after `bun install` in web/; no provider is touched.
import { createRequire } from "node:module";
import { readFileSync, mkdirSync } from "node:fs";

const TREE = process.env.PR568_QA_TREE;
const require = createRequire(`${TREE}/web/package.json`);
const { chromium } = require("@playwright/test");
const IDS = JSON.parse(readFileSync(process.env.PR568_QA_IDS_FILE, "utf-8"));
const OUT = `${TREE}/docs/reports/evidence/568/browser`;
mkdirSync(OUT, { recursive: true });
const API = `http://127.0.0.1:${process.env.PR568_QA_API_PORT ?? "8568"}/api/v1`;
const WEB = `http://127.0.0.1:${process.env.PR568_QA_WEB_PORT ?? "3568"}`;

const COPY = {
  en: { open: "Where Argus looked ›", title: "Where Argus looked", note: "Encontré fuentes" },
  "es-419": { open: "Dónde buscó Argus ›", title: "Dónde buscó Argus", note: "Encontré fuentes" },
};

async function setLanguage(language) {
  const response = await fetch(`${API}/me`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) throw new Error(`PATCH /me ${response.status} ${await response.text()}`);
}

const browser = await chromium.launch();
const report = [];
for (const language of ["en", "es-419"]) {
  await setLanguage(language);
  for (const [width, height, label] of [[1280, 900, "desktop"], [390, 844, "mobile"]]) {
    const context = await browser.newContext({ viewport: { width, height }, isMobile: width < 768, deviceScaleFactor: 2 });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(`${WEB}/chat?conversation=${IDS[language]}`, { waitUntil: "networkidle" });
    // The withheld note is the backend's own, composed per language at seed time.
    const note = language === "en" ? "I found sources, but couldn't verify" : "Encontré fuentes, pero no pude verificar";
    await page.getByText(note, { exact: false }).first().waitFor({ timeout: 30000 });
    const open = page.getByTestId("research-sources-open");
    await open.waitFor({ timeout: 15000 });
    const buttonText = (await open.innerText()).trim();
    await page.screenshot({ path: `${OUT}/withheld-turn-${label}-${language}.png`, fullPage: false });
    await open.click();
    const dialogTitle = page.getByText(COPY[language].title, { exact: true }).first();
    await dialogTitle.waitFor({ timeout: 15000 });
    await page.waitForTimeout(600);
    const bodyText = await page.locator("body").innerText();
    await page.screenshot({ path: `${OUT}/where-argus-looked-${label}-${language}.png`, fullPage: false });
    report.push({
      language, label, buttonText,
      drawerTitleSeen: bodyText.includes(COPY[language].title),
      loanPageListed: bodyText.includes("Préstamo Emprendimiento Popular"),
      domainListed: bodyText.includes("popularenlinea.com"),
      oldSourcesTitle: bodyText.includes("Sources Argus read") || bodyText.includes("Fuentes que Argus consultó"),
      pageErrors: errors,
    });
    await context.close();
  }
}
await browser.close();
console.log(JSON.stringify(report, null, 2));
