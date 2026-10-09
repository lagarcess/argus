// Step 5 search probe: the /biz shell's Search, given a Business merchant.
import { createRequire } from "module";
import { readFileSync, writeFileSync } from "fs";
import { join } from "path";
const require = createRequire("/Users/garces/Documents/projects/repos/argus-worktrees/business-pilot-spaces/web/package.json");
const { chromium } = require("playwright");
const HERE = new URL(".", import.meta.url).pathname;
const OUT = process.argv[2];
const users = Object.fromEntries(readFileSync(join(HERE, "users.env"), "utf8").split("\n").filter((l) => l.includes("=")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "en-US" })).newPage();
const searchCalls = [];
page.on("request", (r) => { const u = new URL(r.url()); if (/search/i.test(u.pathname)) searchCalls.push(`${r.method()} ${u.pathname}?${[...u.searchParams.keys()].join("&")}`); });
await page.goto("http://localhost:3621/biz");
await page.waitForURL(/auth=login/);
await page.locator('input[type="email"]').fill(users.OWNER_A_EMAIL);
await page.locator('input[type="password"]').fill(users.OWNER_A_PASSWORD);
await page.locator('button[type="submit"]').last().click();
await page.waitForURL(/\/biz/);
await page.getByTestId("business-sidebar-nav").waitFor();
await page.waitForLoadState("networkidle");
await page.getByRole("button", { name: /^Search/ }).first().click();
const input = page.getByPlaceholder(/Search Argus/);
await input.waitFor();
for (const q of ["Ferretería", "Colmado"]) {
  await input.fill(q);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: join(OUT, `search-${q === "Colmado" ? "colmado" : "ferreteria"}.png`) });
}
const dialogText = (await page.getByRole("dialog").first().innerText().catch(() => page.locator("body").innerText())).replace(/\s+/g, " ");
writeFileSync(join(OUT, "search-probe.json"), JSON.stringify({ found_merchant: /Ferreter|Colmado/i.test(dialogText.replace(/Search Argus/g, "")), dialog_text: dialogText.slice(0, 300), search_requests: searchCalls }, null, 1));
console.log(readFileSync(join(OUT, "search-probe.json"), "utf8"));
await browser.close();
