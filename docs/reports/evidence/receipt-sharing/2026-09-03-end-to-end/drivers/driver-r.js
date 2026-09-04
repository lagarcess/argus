const { createRequire } = require("module");
const req = createRequire(process.env.WEB_PKG);
const { chromium } = req("@playwright/test");
const fs = require("fs");
const OUT = process.env.OUT;
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-US", storageState: OUT + "/owner-state.json" });
  const page = await ctx.newPage();
  try {
    await page.goto("http://localhost:3000/chat", { waitUntil: "networkidle", timeout: 120000 });
    const composer = page.locator("textarea, [contenteditable='true'], input[placeholder]").first();
    await composer.waitFor({ timeout: 60000 });
    await composer.click();
    await composer.fill("What has been going on with NVDA lately and why is the stock moving?");
    await page.keyboard.press("Enter");
    // Wait for the sources panel or a settled assistant answer.
    const sources = page.getByText(/sources|fuentes/i).first();
    await sources.waitFor({ timeout: 240000 }).catch(() => {});
    await page.waitForTimeout(4000);
    await page.screenshot({ path: OUT + "/r1-research.png", fullPage: true });
    fs.writeFileSync(OUT + "/r1-research-body.txt", await page.locator("body").innerText());
    fs.writeFileSync(OUT + "/r1-url.txt", page.url());
    console.log("RESEARCH_URL=" + page.url());
  } catch (e) {
    await page.screenshot({ path: OUT + "/r-fail.png", fullPage: true }).catch(() => {});
    console.error("FAIL", e.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
