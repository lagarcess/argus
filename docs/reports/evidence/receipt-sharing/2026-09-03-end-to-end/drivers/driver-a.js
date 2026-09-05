const { createRequire } = require("module");
const req = createRequire(process.env.WEB_PKG);
const { chromium } = req("@playwright/test");
const fs = require("fs");
const OUT = process.env.OUT;
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-US" });
  const page = await ctx.newPage();
  page.on("console", (m) => { if (m.type() === "error") fs.appendFileSync(OUT + "/owner-console.log", m.text() + "\n"); });
  try {
    await page.goto("http://localhost:3000/", { waitUntil: "networkidle", timeout: 120000 });
    await page.screenshot({ path: OUT + "/a0-landing.png" });
    const composer = page.locator("textarea, [contenteditable='true'], input[placeholder]").first();
    await composer.waitFor({ timeout: 60000 });
    await composer.click();
    await composer.fill("Test buying AAPL and holding it from January 2, 2024 to March 1, 2024");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2000);
    const stillTyped = (await composer.inputValue().catch(() => "")) || "";
    if (stillTyped.includes("AAPL")) {
      await page.getByRole("button", { name: /send/i }).first().click();
    }
    const runChip = page.getByRole("button", { name: /run (the )?(back)?test|run this|run it|run now/i }).first();
    await runChip.waitFor({ timeout: 180000 });
    await page.screenshot({ path: OUT + "/a1-confirmation.png", fullPage: true });
    await runChip.click();
    const share = page.getByRole("button", { name: /share this/i }).first();
    await share.waitFor({ timeout: 240000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: OUT + "/a2-result.png", fullPage: true });
    fs.writeFileSync(OUT + "/owner-result-body.txt", await page.locator("body").innerText());
    await share.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: OUT + "/a3-compose.png", fullPage: true });
    await page.locator("#receipt-owner-note").fill("Flat two months, the drawdown surprised me.");
    await page.getByRole("button", { name: /make the link/i }).click();
    const code = page.locator("code", { hasText: "/r/" }).first();
    await code.waitFor({ timeout: 60000 });
    const url = (await code.textContent()).trim();
    await page.waitForTimeout(500);
    await page.screenshot({ path: OUT + "/a4-created.png", fullPage: true });
    await page.getByRole("button", { name: /copy link/i }).first().click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: OUT + "/a5-copied.png", fullPage: true });
    fs.writeFileSync(OUT + "/receipt-url.txt", url);
    fs.writeFileSync(OUT + "/owner-page-url.txt", page.url());
    fs.writeFileSync(OUT + "/owner-created-body.txt", await page.locator("body").innerText());
    await ctx.storageState({ path: OUT + "/owner-state.json" });
    console.log("RECEIPT_URL=" + url);
    console.log("OWNER_URL=" + page.url());
  } catch (e) {
    await page.screenshot({ path: OUT + "/a-fail.png", fullPage: true }).catch(() => {});
    fs.writeFileSync(OUT + "/a-fail-body.txt", await page.locator("body").innerText().catch(() => ""));
    console.error("FAIL", e.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
