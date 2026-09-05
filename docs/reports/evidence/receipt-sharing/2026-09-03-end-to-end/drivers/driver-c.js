const { createRequire } = require("module");
const req = createRequire(process.env.WEB_PKG);
const { chromium } = req("@playwright/test");
const fs = require("fs");
const OUT = process.env.OUT;
const URL = fs.readFileSync(OUT + "/receipt-url.txt", "utf8").trim();
const API = "http://127.0.0.1:8000/api/v1";
const ARTIFACT = process.env.ARTIFACT;
const CONV = process.env.CONV;
const log = (...a) => console.log(...a);
(async () => {
  const browser = await chromium.launch();
  async function capture(tag, opts, url = URL) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: OUT + `/${tag}.png`, fullPage: true });
    fs.writeFileSync(OUT + `/${tag}-body.txt`, await page.locator("body").innerText());
    return { ctx, page };
  }
  // B2: Spanish phone, desktop, and the only action.
  try {
    const es = await capture("b-phone-es", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "es-419", extraHTTPHeaders: { "Accept-Language": "es-419,es;q=0.9" } });
    await es.ctx.close();
    const desk = await capture("b-desktop-en", { viewport: { width: 1280, height: 900 }, locale: "en-US", extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" } });
    await desk.ctx.close();
    const en = await capture("b-phone-en-cta", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "en-US", extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" } });
    const cta = en.page.getByRole("link", { name: /test your own idea|prueba|pon a prueba/i }).first();
    await cta.waitFor({ timeout: 20000 });
    fs.writeFileSync(OUT + "/b-cta-href.txt", (await cta.getAttribute("href")) || "");
    await cta.click();
    await en.page.waitForLoadState("networkidle", { timeout: 120000 }).catch(() => {});
    await en.page.waitForTimeout(1500);
    fs.writeFileSync(OUT + "/b-try-argus-landing-url.txt", en.page.url());
    await en.page.screenshot({ path: OUT + "/b-try-argus-landing.png" });
    fs.writeFileSync(OUT + "/b-try-argus-landing-body.txt", await en.page.locator("body").innerText());
    log("B2 ok; landed at", en.page.url());
    await en.ctx.close();
  } catch (e) { log("B2 FAIL", e.message); }

  // C: owner Data Controls -> Shared links -> Take it down.
  const octx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "en-US", storageState: OUT + "/owner-state.json" });
  const op = await octx.newPage();
  try {
    await op.goto("http://localhost:3000/chat", { waitUntil: "networkidle", timeout: 120000 });
    await op.locator("nextjs-portal").evaluateAll((els) => els.forEach((e) => e.remove())).catch(() => {});
    const settings = op.getByRole("button", { name: /^settings$|ajustes/i }).first();
    await settings.waitFor({ timeout: 30000 });
    await settings.click();
    await op.waitForTimeout(600);
    await op.screenshot({ path: OUT + "/c1-settings-flyout.png" });
    const data = op.getByText(/^Data Controls$/).first();
    await data.waitFor({ timeout: 15000 });
    await data.hover();
    await op.waitForTimeout(400);
    await data.click().catch(() => {});
    await op.waitForTimeout(600);
    await op.screenshot({ path: OUT + "/c2-data-controls.png" });
    const shared = op.getByText(/^Shared links$/).first();
    await shared.waitFor({ timeout: 15000 });
    await shared.click();
    await op.waitForTimeout(1200);
    await op.screenshot({ path: OUT + "/c3-shared-links.png" });
    fs.writeFileSync(OUT + "/c3-shared-links-body.txt", await op.locator("body").innerText());
    const revoke = op.getByRole("button", { name: /take it down/i }).first();
    await revoke.waitFor({ timeout: 15000 });
    await revoke.click();
    await op.waitForTimeout(400);
    await op.screenshot({ path: OUT + "/c4-confirm.png" });
    await op.getByRole("button", { name: /sure\?/i }).first().click();
    await op.waitForTimeout(1500);
    await op.screenshot({ path: OUT + "/c5-revoked.png" });
    fs.writeFileSync(OUT + "/c5-revoked-body.txt", await op.locator("body").innerText());
    log("C ok");
  } catch (e) { await op.screenshot({ path: OUT + "/c-fail.png" }).catch(() => {}); log("C FAIL", e.message); }

  // Tombstone as a stranger, both languages.
  try {
    const t1 = await capture("d-tombstone-phone-en", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, locale: "en-US", extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" } });
    fs.writeFileSync(OUT + "/d-tombstone-meta.json", JSON.stringify({ title: await t1.page.title(), metas: await t1.page.$$eval("meta", (els) => els.map((e) => [e.getAttribute("name") || e.getAttribute("property"), e.getAttribute("content")]).filter((x) => x[0] && /robots|og:|description/.test(x[0]))) }, null, 2));
    const og = await t1.page.request.get(URL + "/opengraph-image");
    fs.writeFileSync(OUT + "/d-tombstone-og.png", await og.body());
    log("tombstone og status", og.status());
    await t1.ctx.close();
    const t2 = await capture("d-tombstone-phone-es", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, locale: "es-419", extraHTTPHeaders: { "Accept-Language": "es-419,es;q=0.9" } });
    await t2.ctx.close();
    log("D ok");
  } catch (e) { log("D FAIL", e.message); }

  // E: re-share, then delete the chat behind it, then read the link again.
  try {
    const r = octx.request;
    const created = await (await r.post(`${API}/evidence-artifacts/${ARTIFACT}/public-excerpt`, { data: { owner_note: null } })).json();
    const pub2 = created.receipt.public_id;
    fs.writeFileSync(OUT + "/e-second-receipt.json", JSON.stringify(created, null, 2));
    const before = await (await r.get(`${API}/public/receipts/${pub2}`)).json();
    const del = await r.delete(`${API}/conversations/${CONV}`);
    const after = await (await r.get(`${API}/public/receipts/${pub2}`)).json();
    const list = await (await r.get(`${API}/public-excerpts`)).json();
    fs.writeFileSync(OUT + "/e-owner-list-after-delete.json", JSON.stringify(list, null, 2));
    log("E: second link", pub2, "| before delete:", before.status, "| delete status", del.status(), "| after delete:", after.status, "| list reasons:", list.items.map((i) => i.revocation_reason));
    // Recreate on a deleted chat must refuse.
    const again = await r.post(`${API}/evidence-artifacts/${ARTIFACT}/public-excerpt`, { data: { owner_note: null } });
    log("E: re-share after delete ->", again.status(), (await again.text()).slice(0, 200));
    await op.reload({ waitUntil: "networkidle" }).catch(() => {});
    await op.waitForTimeout(800);
    await op.locator("nextjs-portal").evaluateAll((els) => els.forEach((e) => e.remove())).catch(() => {});
    await op.getByRole("button", { name: /^settings$|ajustes/i }).first().click().catch(() => {});
    await op.waitForTimeout(500);
    const d2 = op.getByText(/^Data Controls$/).first();
    await d2.hover().catch(() => {});
    await d2.click().catch(() => {});
    await op.waitForTimeout(500);
    await op.getByText(/^Shared links$/).first().click().catch(() => {});
    await op.waitForTimeout(1200);
    await op.screenshot({ path: OUT + "/e-list-after-delete.png" });
    fs.writeFileSync(OUT + "/e-list-after-delete-body.txt", await op.locator("body").innerText());
    log("E ok");
  } catch (e) { log("E FAIL", e.message); }
  await octx.close();
  await browser.close();
})().catch((e) => { console.error("FAIL", e.message); process.exit(1); });
