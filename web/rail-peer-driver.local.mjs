// Captures the reworked peer flow: rows on the ordinary Try-next surface,
// motion + single Undo toast on add, restoration on undo.
import { chromium } from "@playwright/test";
import { mkdirSync } from "fs";

const BASE = process.env.RAIL_WEB_BASE || "http://localhost:3100";
const OUT = process.env.RAIL_EVIDENCE_OUT || "./rail-evidence";
const LANG = process.env.RAIL_LANG || "en";
mkdirSync(OUT, { recursive: true });

const run = async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  await context.addInitScript((lng) => {
    window.localStorage.setItem("i18nextLng", lng);
  }, LANG === "es" ? "es-419" : "en");
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  await page.request.patch("http://127.0.0.1:8000/api/v1/me", {
    data: { language: LANG === "es" ? "es-419" : "en" },
  });
  const suffix = LANG === "es" ? "es" : "en";
  const title =
    LANG === "es" ? "Prueba de rivales de streaming" : "Streaming rivals test";

  await page.goto(`${BASE}/chat`);
  await page.waitForTimeout(3500);
  await page
    .getByRole("button", { name: /Recents|Recientes/ })
    .first()
    .click();
  await page.waitForTimeout(1500);
  await page.getByText(title, { exact: true }).first().click();
  await page.waitForTimeout(3000);
  const offer = page
    .locator("button", { hasText: /Add .*\[WBD\]|Agregar .*\[WBD\]/ })
    .first();
  await offer.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/04-peer-rows-${suffix}.png` });
  await offer.click();
  await page.waitForTimeout(2500);
  // The single calm toast carrying Undo is still on screen here.
  await page.screenshot({ path: `${OUT}/05-peer-added-undo-toast-${suffix}.png` });
  await page
    .getByRole("button", { name: /^(Undo|Deshacer)$/ })
    .first()
    .click();
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${OUT}/06-peer-undo-restored-${suffix}.png` });
  await browser.close();
  console.log(`peer flow done (${suffix})`);
};

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
