const { createRequire } = require("module");
const req = createRequire(process.env.WEB_PKG);
const { chromium } = req("@playwright/test");
const fs = require("fs");
const OUT = process.env.OUT;
const URL = fs.readFileSync(OUT + "/receipt-url.txt", "utf8").trim();
(async () => {
  const browser = await chromium.launch();
  async function view(tag, opts) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    const resp = await page.goto(URL, { waitUntil: "networkidle", timeout: 120000 });
    fs.writeFileSync(OUT + `/b-${tag}-headers.json`, JSON.stringify(resp.headers(), null, 2));
    await page.waitForTimeout(800);
    await page.screenshot({ path: OUT + `/b-${tag}.png`, fullPage: true });
    fs.writeFileSync(OUT + `/b-${tag}-body.txt`, await page.locator("body").innerText());
    fs.writeFileSync(OUT + `/b-${tag}-dom.html`, await page.content());
    const title = await page.title();
    const metas = await page.$$eval("meta", (els) => els.map((e) => [e.getAttribute("name") || e.getAttribute("property"), e.getAttribute("content")]).filter((x) => x[0]));
    fs.writeFileSync(OUT + `/b-${tag}-meta.json`, JSON.stringify({ title, metas }, null, 2));
    return { ctx, page };
  }
  const en = await view("phone-en", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "en-US", extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" } });
  // The only action: Try Argus. Record where a stranger lands.
  const cta = en.page.getByRole("link", { name: /try argus|prueba argus|probar argus/i }).first();
  await cta.waitFor({ timeout: 20000 });
  await cta.click();
  await en.page.waitForLoadState("networkidle", { timeout: 120000 }).catch(() => {});
  await en.page.waitForTimeout(1500);
  fs.writeFileSync(OUT + "/b-try-argus-landing-url.txt", en.page.url());
  await en.page.screenshot({ path: OUT + "/b-try-argus-landing.png", fullPage: false });
  fs.writeFileSync(OUT + "/b-try-argus-landing-body.txt", await en.page.locator("body").innerText());
  await en.ctx.close();
  const es = await view("phone-es", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "es-419", extraHTTPHeaders: { "Accept-Language": "es-419,es;q=0.9" } });
  await es.ctx.close();
  const desk = await view("desktop-en", { viewport: { width: 1280, height: 900 }, locale: "en-US", extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" } });
  // The preview card a platform fetches.
  const og = await desk.page.request.get(URL + "/opengraph-image");
  fs.writeFileSync(OUT + "/b-og-headers.json", JSON.stringify(og.headers(), null, 2));
  fs.writeFileSync(OUT + "/b-og.png", await og.body());
  console.log("og status", og.status(), "bytes", (await og.body()).length);
  await desk.ctx.close();
  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error("FAIL", e.message); process.exit(1); });
