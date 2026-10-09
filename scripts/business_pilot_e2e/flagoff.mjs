// Step 8: Business flag unset. Phase "api": API restarted without the flag, web
// still on. Phase "web": web restarted without NEXT_PUBLIC_BUSINESS_PILOT_ENABLED.
import { createRequire } from "module";
import { execFileSync } from "child_process";
import { readFileSync, appendFileSync } from "fs";
import { join } from "path";

const WORKTREE = "/Users/garces/Documents/projects/repos/argus-worktrees/business-pilot-spaces";
const require = createRequire(join(WORKTREE, "web", "package.json"));
const { chromium } = require("playwright");

const HERE = new URL(".", import.meta.url).pathname;
const [OUT, PHASE] = process.argv.slice(2);
const APP = "http://localhost:3621";
const API = "http://127.0.0.1:8621/api/v1";
const envFile = (name) =>
  Object.fromEntries(
    readFileSync(join(HERE, name), "utf8")
      .split("\n")
      .filter((line) => line.includes("="))
      .map((line) => [line.slice(0, line.indexOf("=")), line.slice(line.indexOf("=") + 1).replace(/^"|"$/g, "")]),
  );
const stack = envFile("stack.env");
const users = envFile("users.env");
const ids = JSON.parse(readFileSync(join(OUT, "ids.json"), "utf8"));
const LOG = join(OUT, "evidence-log.md");
const md = (text) => appendFileSync(LOG, text.replaceAll(ids.webId, "<web receipt>") + "\n");
const results = [];
const check = (name, ok, detail = "") => {
  results.push(ok);
  md(`- ${ok ? "PASS" : "FAIL"}: ${name}${detail ? ` (${detail})` : ""}`);
  console.log(ok ? "PASS" : "FAIL", name, detail);
};

const token = await fetch(`${stack.API_URL}/auth/v1/token?grant_type=password`, {
  method: "POST",
  headers: { apikey: stack.ANON_KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ email: users.OWNER_A_EMAIL, password: users.OWNER_A_PASSWORD }),
}).then((r) => r.json()).then((b) => b.access_token);

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "en-US" })).newPage();
await page.goto(`${APP}/?auth=login`);
await page.waitForLoadState("networkidle");
let signedIn = false;
if (await page.locator('input[type="password"]').count()) {
  await page.locator('input[type="email"]').fill(users.OWNER_A_EMAIL);
  await page.locator('input[type="password"]').fill(users.OWNER_A_PASSWORD);
  await page.locator('button[type="submit"]').last().click();
  await page.waitForURL((url) => !url.search.includes("auth=login"), { timeout: 30_000 });
  signedIn = true;
}
const bizResponse = await page.goto(`${APP}/biz`);
await page.waitForTimeout(4000);
await page.screenshot({ path: join(OUT, `flag-off-${PHASE}.png`) });
const bodyText = (await page.locator("body").innerText()).replace(/\s+/g, " ").slice(0, 240);
const navVisible = await page.getByTestId("business-sidebar-nav").isVisible().catch(() => false);
await browser.close();

if (PHASE === "api") {
  const probes = {};
  for (const [method, path] of [
    ["GET", "/business/space"],
    ["POST", "/business/space"],
    ["GET", "/business/workspace"],
    ["GET", "/business/receipts?view=all"],
    ["GET", `/business/receipts/${ids.webId}`],
    ["GET", `/business/receipts/${ids.webId}/source`],
    ["GET", "/business/expenses?from=2026-10-01&to=2026-10-31"],
    ["GET", "/business/overview?from=2026-10-01&to=2026-10-31"],
    ["GET", "/business/updates"],
  ]) {
    for (const [who, auth] of [["A", { Authorization: `Bearer ${token}` }], ["signed out", {}]]) {
      const response = await fetch(API + path, {
        method,
        headers: { ...auth, ...(method === "POST" ? { "Content-Type": "application/json" } : {}) },
        body: method === "POST" ? JSON.stringify({ language: "en" }) : undefined,
      });
      const body = await response.json().catch(() => null);
      probes[`${who}: ${method} ${path.split("?")[0]}`] = `${response.status} ${body?.code ?? ""}`.trim();
    }
  }
  const personal = await fetch(`${API}/financial-accounts`, { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.status);
  const flag = execFileSync("grep", ["-c", "business flag <unset>", join(HERE, "api.log")], { encoding: "utf8" }).trim();
  md(
    `\n## 8. Flag off\n\n8a. The API was stopped and started again with ARGUS_BUSINESS_PILOT_ENABLED removed from its env (launcher printed "business flag <unset>": ${flag !== "0"}). The web still had its flag on.\n\n` +
      `\`\`\`json\n${JSON.stringify(probes, null, 1)}\n\`\`\`\n\n` +
      `Personal GET /financial-accounts as A -> ${personal}. Owner A ${signedIn ? "signed in and " : ""}opened /biz -> HTTP ${bizResponse?.status()}; Business nav visible: ${navVisible}; page text starts "${bodyText}". Screenshot flag-off-api.png.\n`,
  );
  check("every /api/v1/business route returns 404 with the flag unset, signed in or out", Object.values(probes).every((v) => v.startsWith("404")), "");
  check("Personal routes keep working", personal === 200);
} else {
  const anon = await fetch(`${APP}/biz`, { redirect: "manual" });
  const curl = anon.status;
  const anonNotFound = (await anon.text()).includes("This page could not be found");
  const missing = await fetch(`${APP}/no-such-page`, { redirect: "manual" }).then((r) => r.status);
  md(
    `\n8b. The web was stopped and started again without NEXT_PUBLIC_BUSINESS_PILOT_ENABLED. Owner A ${signedIn ? "signed in and " : ""}opened /biz -> HTTP ${bizResponse?.status()}; Business nav visible: ${navVisible}; page text starts "${bodyText}". A signed-out GET /biz -> HTTP ${curl}, body is the Next.js not-found page: ${anonNotFound}. For comparison, a path with no route (/no-such-page) -> HTTP ${missing}. Screenshot flag-off-web.png.\n`,
  );
  check("/biz is not available with the flag unset (not-found page, no Business UI)", !navVisible && bodyText.includes("This page could not be found") && anonNotFound, `HTTP status signed in ${bizResponse?.status()}, signed out ${curl}`);
}
process.exit(results.every(Boolean) ? 0 : 1);
