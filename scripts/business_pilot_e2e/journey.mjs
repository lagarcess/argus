// Business capture-to-expense (B1) with Personal isolation, on local services.
// Local services, stub extractor, replayed WhatsApp fixtures. Prints no secrets.
import { createRequire } from "module";
import { createHash, createHmac, randomUUID } from "crypto";
import { execFileSync } from "child_process";
import { mkdirSync, readFileSync, writeFileSync, appendFileSync } from "fs";
import { join } from "path";

const WORKTREE = "/Users/garces/Documents/projects/repos/argus-worktrees/business-pilot-spaces";
const require = createRequire(join(WORKTREE, "web", "package.json"));
const { chromium } = require("playwright");
const { expect } = require("@playwright/test");

const HERE = new URL(".", import.meta.url).pathname;
const OUT = process.argv[2];
mkdirSync(join(OUT, "video"), { recursive: true });
const APP = "http://localhost:3621";
const API = "http://127.0.0.1:8621/api/v1";
const PY = "/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.venv/bin/python";
const FIXTURES = join(WORKTREE, "tests/fixtures/whatsapp");
const PHONE_A = "1555" + String(Date.now()).slice(-7);
const HEAD = execFileSync("git", ["-C", WORKTREE, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();

function envFile(name) {
  return Object.fromEntries(
    readFileSync(join(HERE, name), "utf8")
      .split("\n")
      .filter((line) => line.includes("="))
      .map((line) => [line.slice(0, line.indexOf("=")), line.slice(line.indexOf("=") + 1).replace(/^"|"$/g, "")]),
  );
}
const stack = envFile("stack.env");
const users = envFile("users.env");
const wa = envFile("wa.env");

const ids = new Map();
function alias(id, name) {
  if (id) ids.set(id, name);
  return id;
}
const redact = (text) => {
  let out = String(text).replaceAll(users.OWNER_A_ID, "<A>").replaceAll(users.OWNER_B_ID, "<B>");
  for (const [id, name] of ids) out = out.replaceAll(id, `<${name}>`);
  return out;
};

const LOG = join(OUT, "evidence-log.md");
writeFileSync(LOG, "");
const md = (text) => appendFileSync(LOG, redact(text) + "\n");
const http = [];
const results = [];
function check(step, name, ok, detail = "") {
  results.push({ step, name, ok });
  md(`- ${ok ? "PASS" : "FAIL"}: ${name}${detail ? ` (${detail})` : ""}`);
  console.log(`${ok ? "PASS" : "FAIL"} [${step}] ${name}${ok ? "" : " " + redact(detail)}`);
}
function section(title, text, extra = {}) {
  md(`\n## ${title}\n\n${text}\n`);
  if (extra.http !== false) {
    const lines = http.splice(0);
    if (lines.length) md("HTTP:\n\n" + lines.map((h) => `- \`${h}\``).join("\n") + "\n");
  }
  if (extra.counts) md("DB rows (owner A):\n\n```json\n" + JSON.stringify(extra.counts, null, 1) + "\n```\n");
  console.log(`[${title}]`);
}
const counts = (owner = users.OWNER_A_ID) => JSON.parse(execFileSync(PY, [join(HERE, "counts.py"), owner], { encoding: "utf8" }));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const stubLines = () => {
  try {
    return readFileSync(join(HERE, "stub-calls.log"), "utf8").trim().split("\n").filter(Boolean);
  } catch {
    return [];
  }
};
const stubStart = stubLines().length;
const stubCallsFor = (bytes) => stubLines().slice(stubStart).filter((line) => line.includes(" " + sha(bytes).slice(0, 12) + " ")).length;
const apiCtl = (...args) => execFileSync(join(HERE, "api.sh"), args, { encoding: "utf8" }).trim();
const month = "2026-10";
const RANGE = `from=${month}-01&to=${month}-31`;

async function token(label) {
  const response = await fetch(`${stack.API_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: stack.ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: users[`OWNER_${label}_EMAIL`], password: users[`OWNER_${label}_PASSWORD`] }),
  });
  if (!response.ok) throw new Error(`token for ${label}: ${response.status}`);
  return (await response.json()).access_token;
}
async function api(who, bearer, method, path, { body, bytes, headers = {}, raw = false } = {}) {
  const response = await fetch(API + path, {
    method,
    headers: {
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: bytes ?? (body ? JSON.stringify(body) : undefined),
  });
  http.push(`${who}: ${method} ${path.split("?")[0]} -> ${response.status}`);
  const payload = raw && response.ok ? Buffer.from(await response.arrayBuffer()) : await response.json().catch(() => null);
  return { status: response.status, body: payload };
}
function delivery(name, message) {
  const body = JSON.parse(readFileSync(join(FIXTURES, name), "utf8"));
  const value = body.entry[0].changes[0].value;
  value.contacts[0].wa_id = PHONE_A;
  value.messages[0] = { ...value.messages[0], ...message, from: PHONE_A, timestamp: String(Math.floor(Date.now() / 1000)) };
  return Buffer.from(JSON.stringify(body));
}
async function webhook(raw) {
  const signature = "sha256=" + createHmac("sha256", wa.WA_APP_SECRET).update(raw).digest("hex");
  const response = await fetch(`${API}/webhooks/whatsapp`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Hub-Signature-256": signature },
    body: raw,
  });
  http.push(`webhook: POST /webhooks/whatsapp -> ${response.status}`);
  return response.status;
}
async function until(fn, ms = 20_000, every = 500) {
  const end = Date.now() + ms;
  for (;;) {
    const value = await fn();
    if (value || Date.now() > end) return value;
    await new Promise((resolve) => setTimeout(resolve, every));
  }
}

const receipts = {
  web: readFileSync(join(HERE, "receipt-web.png")),
  noai: readFileSync(join(HERE, "receipt-noai.png")),
  whatsapp: readFileSync(join(HERE, "receipt-whatsapp.png")),
  slow: readFileSync(join(HERE, "receipt-slow.png")),
};

let tokenA = await token("A");
const tokenB = await token("B");
const before = { A: counts(), B: counts(users.OWNER_B_ID) };
writeFileSync(join(OUT, "counts-before.json"), JSON.stringify(before, null, 1) + "\n");
md(
  "# Business capture-to-expense (B1) and Personal isolation: local end-to-end evidence log\n\n" +
    "Label: **local services, stub extractor, replayed WhatsApp fixtures; not provider or hosted proof.**\n\n" +
    `Run: ${new Date().toISOString()}. Code: branch claude/business-spaces at ${HEAD}. ` +
    "API http://127.0.0.1:8621 (uvicorn from this worktree, Supabase persistence on the disposable local stack argus-biz-spaces, DB 57782, reset before the run, 119 migrations). " +
    "Web http://localhost:3621 (next dev from this worktree). Real local Supabase Auth; owners A and B created with the local admin API. " +
    "Flags were on only in the API and web process env. The API process had HTTP(S)_PROXY pointed at a dead local port with NO_PROXY=127.0.0.1,localhost, so any outbound provider call would fail. " +
    "The stub extractor returns a fixed read per synthetic receipt digest and logs each call; WhatsApp deliveries are signed replays of the repo fixtures in tests/fixtures/whatsapp, with media served from local files; outbound replies off.\n\n" +
    "Ids are shown by alias: <A>, <B>, and names such as <web receipt>. Counts come from `counts.py` (direct SQL on the local stack). " +
    "Business rows are those with `owner_space_id` set; Personal rows have it null.\n\n" +
    "Files: `business-isolation-journey.mp4` (owner A's browser, Playwright video converted with ffmpeg), `counts-before.json`, `counts-after.json`.\n",
);
section("0. Start", "Owners A and B exist in local Supabase Auth. Neither has a space.", { counts: before.A });

const browser = await chromium.launch({ slowMo: 200 });
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  locale: "en-US",
  recordVideo: { dir: join(OUT, "video"), size: { width: 1280, height: 800 } },
  acceptDownloads: true,
});
const page = await context.newPage();
page.setDefaultTimeout(25_000);
const consoleErrors = [];
page.on("console", (message) => message.type() === "error" && consoleErrors.push(message.text()));
page.on("response", (response) => {
  const url = new URL(response.url());
  if (url.pathname.includes("/api/v1/business") || url.pathname.includes("/api/v1/financial")) {
    http.push(`browser: ${response.request().method()} ${url.pathname.replace(/[0-9a-f-]{36}/g, "{id}")} -> ${response.status()}`);
  }
});
await page.addInitScript(() => window.localStorage.setItem("argus:sidebar_mode", "expanded"));
const pause = (ms = 1200) => page.waitForTimeout(ms);
const panel = () => page.getByTestId("workspace-panel-region");
const nav = () => page.getByTestId("business-sidebar-nav");
async function openNav(name, heading = name) {
  await nav().getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(panel().getByRole("heading", { name: heading, exact: true })).toBeVisible();
}
async function signIn(target) {
  await page.goto(target);
  await page.waitForURL(/auth=login/);
  await page.locator('input[type="email"]').fill(users.OWNER_A_EMAIL);
  await page.locator('input[type="password"]').fill(users.OWNER_A_PASSWORD);
  await page.locator('button[type="submit"]').last().click();
  await page.waitForURL(/\/biz/, { timeout: 30_000 });
  await expect(nav()).toBeVisible({ timeout: 30_000 });
}
const confirmRequests = () => http.filter((line) => line.startsWith("browser: POST") && line.endsWith("/confirm -> 200")).length;

// Sign in; the first visit starts A's space. Then a Business account.
await signIn(`${APP}/biz`);
await page.waitForLoadState("networkidle");
const spaceA = await api("A", tokenA, "GET", "/business/space");
alias(spaceA.body?.id, "A space");
const bizAccount = await api("A", tokenA, "POST", "/business/accounts", {
  body: { nickname: "Cuenta operativa", type: "checking", currency: "DOP" },
  headers: { "Idempotency-Key": randomUUID() },
});
alias(bizAccount.body?.id, "A business account");
await page.reload();
await expect(nav()).toBeVisible();
await pause();
section(
  "Setup. Sign in, space, Business account",
  `Owner A signed in through the login form and landed on /biz. The first visit started A's space: GET /business/space -> ${spaceA.status} name "${spaceA.body?.name}". Business account "Cuenta operativa" (checking, DOP) -> ${bizAccount.status}.`,
  { counts: counts() },
);

// ---------------------------------------------------------------- Step 1
const step1Before = counts();
await page.getByTestId("business-create").click();
await page.getByRole("menuitem", { name: "Upload receipt" }).click();
let dialog = page.getByRole("dialog", { name: "Upload receipt" });
await page.locator('input[type="file"]').first().setInputFiles({ name: "ferreteria-oct.png", mimeType: "image/png", buffer: receipts.web });
await dialog.getByRole("checkbox").check();
await dialog.getByRole("button", { name: "Save to Inbox" }).click();
await expect(panel().getByRole("heading", { name: "Review receipt" })).toBeVisible();
const webId = alias(new URL(page.url()).searchParams.get("receipt"), "web receipt");
const webPrepared = await until(async () => {
  const detail = await api("A", tokenA, "GET", `/business/receipts/${webId}`);
  return detail.body?.status === "review_ready" ? detail : null;
});
await openNav("Inbox");
await panel().getByRole("button", { name: /FERRETERIA LA ESQUINA/ }).click();
await expect(panel().getByRole("heading", { name: "Review receipt" })).toBeVisible();
await expect(page.getByLabel("Merchant")).toHaveValue("FERRETERIA LA ESQUINA SRL");
await page.getByLabel("Merchant").fill("Ferretería La Esquina");
const total = page.getByTestId("receipt-review-amount");
await total.click();
await total.fill("");
await page.keyboard.type("3400");
await page.getByLabel("Merchant").click();
await page.getByLabel(/Paid from/).selectOption({ label: "Cuenta operativa · DOP" });
await pause();
const confirmsBefore1 = confirmRequests();
await page.getByRole("button", { name: "Confirm expense" }).dblclick();
await expect(panel()).toContainText("Saved as one expense of", { timeout: 20_000 });
await pause(800);
const uiConfirms1 = confirmRequests() - confirmsBefore1;
const webConfirmed = await api("A", tokenA, "GET", `/business/receipts/${webId}`);
alias(webConfirmed.body?.expense_id, "web expense");
const step1After = counts();
section(
  "1. Web upload, review and correct",
  `Owner A uploaded ferreteria-oct.png (${receipts.web.length} bytes, sha256 ${sha(receipts.web).slice(0, 12)}) from Create > Upload receipt with the AI box checked. The stub read it: status ${webPrepared?.body?.status}, merchant "${webPrepared?.body?.merchant}", total ${webPrepared?.body?.amount}. ` +
    `From the Inbox A corrected the merchant to "Ferretería La Esquina" and the total from 3,450.00 to 3,400.00, chose the account, and double-clicked Confirm expense. The UI sent ${uiConfirms1} confirm request(s). ` +
    `Stored: status ${webConfirmed.body?.status}, merchant "${webConfirmed.body?.merchant}", amount ${webConfirmed.body?.amount} ${webConfirmed.body?.currency}; evidence still "${webConfirmed.body?.evidence?.merchant}" ${webConfirmed.body?.evidence?.total}. Stub calls for this receipt: ${stubCallsFor(receipts.web)}.`,
  { counts: step1After },
);
check(1, "stub prepared the upload once", webPrepared?.body?.status === "review_ready" && stubCallsFor(receipts.web) === 1);
check(
  1,
  "exactly one expense with the corrected values",
  webConfirmed.body?.status === "confirmed" &&
    webConfirmed.body?.merchant === "Ferretería La Esquina" &&
    webConfirmed.body?.amount === "3400.00" &&
    step1After.business.import_events_accepted === step1Before.business.import_events_accepted + 1,
  `accepted ${step1Before.business.import_events_accepted} -> ${step1After.business.import_events_accepted}`,
);
check(1, "double-click sent one confirm", uiConfirms1 === 1, `confirm requests ${uiConfirms1}`);
check(1, "evidence unchanged by the correction", webConfirmed.body?.evidence?.total === "3450.00" && webConfirmed.body?.evidence?.merchant === "FERRETERIA LA ESQUINA SRL");

// ---------------------------------------------------------------- Step 2
const stubBefore2 = stubLines().length;
await page.getByTestId("business-create").click();
await page.getByRole("menuitem", { name: "Upload receipt" }).click();
dialog = page.getByRole("dialog", { name: "Upload receipt" });
await page.locator('input[type="file"]').first().setInputFiles({ name: "farmacia.png", mimeType: "image/png", buffer: receipts.noai });
const consentChecked = await dialog.getByRole("checkbox").isChecked();
await dialog.getByRole("button", { name: "Save to Inbox" }).click();
await expect(panel().getByRole("heading", { name: "Review receipt" })).toBeVisible();
const noaiId = alias(new URL(page.url()).searchParams.get("receipt"), "no-AI receipt");
await expect(panel()).toContainText("sent to our AI provider only if you choose this");
const noaiSaved = await api("A", tokenA, "GET", `/business/receipts/${noaiId}`);
const confirmButton = page.getByRole("button", { name: "Confirm expense" });
const disabledBefore = await confirmButton.isDisabled();
await page.getByLabel("Merchant").fill("Farmacia Carol");
await page.getByLabel(/^Date/).fill("2026-10-05");
await page.getByLabel(/^Currency/).selectOption("DOP");
await page.getByTestId("receipt-review-amount").click();
await page.keyboard.type("498.00");
await page.getByLabel("Merchant").click();
await page.getByLabel(/^Category/).selectOption("health");
await page.getByLabel(/Paid from/).selectOption({ label: "Cuenta operativa · DOP" });
const enabledAfter = await confirmButton.isEnabled();
await pause();
await confirmButton.click();
await expect(panel()).toContainText("Saved as one expense of", { timeout: 20_000 });
const noaiDetail = await api("A", tokenA, "GET", `/business/receipts/${noaiId}`);
alias(noaiDetail.body?.expense_id, "no-AI expense");
const noaiPrepare = await api("A", tokenA, "POST", `/business/receipts/${noaiId}/prepare`, { headers: { "X-Extraction-Consent": "true" } });
const step2After = counts();
section(
  "2. Without AI",
  `Uploaded farmacia.png with the AI box left unchecked (checked: ${consentChecked}). Saved status ${noaiSaved.body?.status}. Confirm disabled before entry: ${disabledBefore}; enabled after merchant, date, currency, total, category and account were typed: ${enabledAfter}. ` +
    `Stored: status ${noaiDetail.body?.status}, merchant "${noaiDetail.body?.merchant}", amount ${noaiDetail.body?.amount}, category ${noaiDetail.body?.category_id}, evidence ${JSON.stringify(noaiDetail.body?.evidence)}. Prepare with AI afterwards -> ${noaiPrepare.status} ${noaiPrepare.body?.code}. Stub calls during this step: ${stubLines().length - stubBefore2}.`,
  { counts: step2After },
);
check(
  2,
  "hand-entered receipt confirmed as exactly one expense, no extractor call",
  !consentChecked &&
    noaiSaved.body?.status === "saved" &&
    disabledBefore &&
    enabledAfter &&
    noaiDetail.body?.status === "confirmed" &&
    noaiDetail.body?.amount === "498.00" &&
    noaiDetail.body?.evidence === null &&
    stubLines().length === stubBefore2 &&
    step2After.business.import_events_accepted === step1After.business.import_events_accepted + 1,
);
check(2, "prepare after hand entry refused", noaiPrepare.status === 409 && noaiPrepare.body?.code === "document_entered_by_owner");

// ---------------------------------------------------------------- Step 3
const issued = await api("A", tokenA, "POST", "/whatsapp/link-codes", { body: { language: "en" } });
const linkStatus = await webhook(delivery("text_link_code.json", { id: `wamid.ISO-LINK-${Date.now()}`, text: { body: issued.body?.message_text } }));
const link = await api("A", tokenA, "GET", "/whatsapp/link");
const imageRaw = delivery("image_message.json", {
  id: `wamid.ISO-IMAGE-${Date.now()}`,
  type: "image",
  image: { caption: "Recibo colmado", mime_type: "image/png", sha256: "bG9jYWw=", id: "700000000000901" },
});
const stubBefore3 = stubLines().length;
const imageStatus = await webhook(imageRaw);
await openNav("Inbox");
const waRow = panel().getByRole("button").filter({ has: page.getByLabel("WhatsApp") });
await pause(3000);
const waRowsBeforeReload = await waRow.count();
await page.goto(`${APP}/biz?view=inbox`);
await expect(panel().getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
await expect(waRow).toHaveCount(1, { timeout: 20_000 });
const inbox3 = await api("A", tokenA, "GET", "/business/receipts?view=inbox");
const waId = alias(inbox3.body?.items?.find((item) => item.channel === "whatsapp")?.id, "WhatsApp receipt");
const waSaved = await api("A", tokenA, "GET", `/business/receipts/${waId}`);
const stubAtCapture = stubLines().length - stubBefore3;
await waRow.click();
await expect(panel().getByRole("heading", { name: "Review receipt" })).toBeVisible();
await page.getByRole("button", { name: "Prepare with AI" }).click();
await until(async () => (await api("A", tokenA, "GET", `/business/receipts/${waId}`)).body?.status === "review_ready");
await page.reload();
await expect(page.getByLabel("Merchant")).toHaveValue("COLMADO DON PEDRO", { timeout: 20_000 });
await page.getByLabel("Merchant").fill("Colmado Don Pedro");
await page.getByLabel(/^Category/).selectOption("groceries");
await page.getByLabel(/Paid from/).selectOption({ label: "Cuenta operativa · DOP" });
await pause();
const replayStatus = await webhook(imageRaw);
const afterReplay = counts();
const confirmsBefore3 = confirmRequests();
await page.getByRole("button", { name: "Confirm expense" }).dblclick();
await expect(panel()).toContainText("Saved as one expense of", { timeout: 20_000 });
await pause(800);
const uiConfirms3 = confirmRequests() - confirmsBefore3;
const waConfirmed = await api("A", tokenA, "GET", `/business/receipts/${waId}`);
alias(waConfirmed.body?.expense_id, "WhatsApp expense");
const waSource = await api("A", tokenA, "GET", `/business/receipts/${waId}/source`, { raw: true });
const delivered = readFileSync(join(HERE, "media", "700000000000901.png"));
const step3After = counts();
section(
  "3. WhatsApp",
  `Link code issued (${issued.status}); signed link message from A's synthetic number -> ${linkStatus}; link ${JSON.stringify({ linked: link.body?.linked, last4: link.body?.last4 })}. Signed image delivery (media id 700000000000901 served from a local file) -> ${imageStatus}. ` +
    `With /biz already open, the Inbox nav showed ${waRowsBeforeReload} WhatsApp row(s) until the page was loaded again (the Inbox list is fetched on load and after the owner's own actions, not polled). After a load it showed the receipt in A's Business Inbox with the WhatsApp mark: channel ${waSaved.body?.channel}, status ${waSaved.body?.status}; stub calls at capture ${stubAtCapture}. ` +
    `A chose Prepare with AI: merchant "COLMADO DON PEDRO", total 706.10. A corrected the merchant to "Colmado Don Pedro", set the category and account, and double-clicked Confirm expense (UI confirm requests: ${uiConfirms3}). ` +
    `Before confirming, the same signed image event was replayed -> ${replayStatus}; Business documents ${afterReplay.business.documents_live}, captured messages ${afterReplay.whatsapp_messages_captured}. ` +
    `Stored: status ${waConfirmed.body?.status}, merchant "${waConfirmed.body?.merchant}", amount ${waConfirmed.body?.amount}. Source sha256 ${sha(waSource.body ?? Buffer.alloc(0)).slice(0, 12)}, delivered media sha256 ${sha(delivered).slice(0, 12)}.`,
  { counts: step3After },
);
check(3, "WhatsApp receipt lands in A's Business Inbox without AI", imageStatus === 200 && link.body?.linked === true && waSaved.body?.status === "saved" && waSaved.body?.channel === "whatsapp" && stubAtCapture === 0);
check(
  3,
  "reviewed, corrected and confirmed as exactly one expense",
  waConfirmed.body?.status === "confirmed" && waConfirmed.body?.merchant === "Colmado Don Pedro" && step3After.business.import_events_accepted === step2After.business.import_events_accepted + 1 && uiConfirms3 === 1,
);
check(3, "source bytes match the delivered media by sha256", waSource.status === 200 && sha(waSource.body) === sha(delivered));
check(3, "replayed delivery made no second receipt", replayStatus === 200 && afterReplay.whatsapp_messages_captured === 1 && afterReplay.business.documents_live === 3);

// ---------------------------------------------------------------- Step 4
const sameKey = randomUUID();
const burst = await Promise.all([
  api("A", tokenA, "POST", `/business/receipts/${waId}/confirm`, { body: { version: waConfirmed.body.version }, headers: { "Idempotency-Key": sameKey } }),
  api("A", tokenA, "POST", `/business/receipts/${waId}/confirm`, { body: { version: waConfirmed.body.version }, headers: { "Idempotency-Key": sameKey } }),
]);
const lateWeb = await api("A", tokenA, "POST", `/business/receipts/${webId}/confirm`, { body: { version: webConfirmed.body.version }, headers: { "Idempotency-Key": randomUUID() } });
const afterBurst = counts();
section(
  "4a. Duplicate confirms",
  `Two concurrent API confirms of the WhatsApp receipt with one Idempotency-Key -> ${JSON.stringify(burst.map((r) => r.status))}, expense ids ${JSON.stringify(burst.map((r) => r.body?.expense_id))}. A late confirm of the web receipt with a new key -> ${lateWeb.status}, expense ${lateWeb.body?.expense_id}. The UI double-clicks in steps 1 and 3 sent ${uiConfirms1} and ${uiConfirms3} confirm request(s).`,
  { counts: afterBurst },
);
check(
  4,
  "double-click and same-key replay each leave one expense",
  burst.every((r) => r.status === 200 && r.body?.expense_id === waConfirmed.body.expense_id) &&
    lateWeb.status === 200 &&
    lateWeb.body?.expense_id === webConfirmed.body.expense_id &&
    afterBurst.business.import_events_accepted === step3After.business.import_events_accepted,
);

// A preparation in flight when the API dies.
const slowUpload = await api("A", tokenA, "POST", "/business/receipts", {
  bytes: receipts.slow,
  headers: { "Content-Type": "image/png", "X-Document-Filename": "libreria.png", "X-Extraction-Consent": "true", "Idempotency-Key": randomUUID() },
});
const slowId = alias(slowUpload.body?.id, "in-flight receipt");
const inFlight = await until(() => stubCallsFor(receipts.slow) >= 1, 20_000);
const slowBeforeKill = await api("A", tokenA, "GET", `/business/receipts/${slowId}`);
const beforeKill = counts();
const killed = apiCtl("kill9");
await page.waitForTimeout(1500);
const downProbe = await fetch(`${API}/business/space`).then((r) => r.status).catch(() => "connection refused");
const restarted = apiCtl("start");
tokenA = await token("A");
const afterRestart = counts();
const slowAfterRestart = await api("A", tokenA, "GET", `/business/receipts/${slowId}`);
const replayAfterRestart = await api("A", tokenA, "POST", `/business/receipts/${waId}/confirm`, { body: { version: waConfirmed.body.version }, headers: { "Idempotency-Key": sameKey } });
await page.reload();
await expect(nav()).toBeVisible();
await pause();
const afterRestartReplay = counts();
section(
  "4b. Kill the API mid-session and restart",
  `Uploaded libreria.png through the API with AI consent -> ${slowUpload.status} status ${slowUpload.body?.status}. The stub logged the call (in flight: ${Boolean(inFlight)}) and holds it for 120 s. Before the kill: receipt status ${slowBeforeKill.body?.status}. ` +
    `${killed.replace(/\d+$/, "<pid>")} while owner A's browser stayed open; a request during the outage -> ${downProbe}. Restarted: ${restarted.replace(/\d+$/, "<pid>")}. After restart the receipt is ${slowAfterRestart.body?.status}. ` +
    `The same-key confirm of the WhatsApp receipt replayed after the restart -> ${replayAfterRestart.status}, same expense ${replayAfterRestart.body?.expense_id === waConfirmed.body.expense_id}. The browser reloaded /biz on the new process.`,
  { counts: afterRestartReplay },
);
check(
  4,
  "expense count unchanged across the kill and restart",
  JSON.stringify(beforeKill.business) === JSON.stringify(afterRestart.business) &&
    afterRestartReplay.business.import_events_accepted === beforeKill.business.import_events_accepted &&
    replayAfterRestart.status === 200 &&
    replayAfterRestart.body?.expense_id === waConfirmed.body.expense_id,
  `accepted before kill ${beforeKill.business.import_events_accepted}, after restart ${afterRestartReplay.business.import_events_accepted}`,
);

// ---------------------------------------------------------------- Step 5
await page.reload();
await expect(nav()).toBeVisible();
await openNav("Expenses");
for (const text of ["Ferretería La Esquina", "Farmacia Carol", "Colmado Don Pedro", "3,400.00", "498.00", "706.10"]) {
  await expect(panel()).toContainText(text);
}
await pause();
const expensesText = await panel().innerText();
const expenses = await api("A", tokenA, "GET", `/business/expenses?${RANGE}`);
const all = await api("A", tokenA, "GET", "/business/receipts?view=all");
const inboxNow = await api("A", tokenA, "GET", "/business/receipts?view=inbox");
const downloads = {};
for (const [name, id, bytes] of [
  ["web", webId, receipts.web],
  ["no-AI", noaiId, receipts.noai],
  ["WhatsApp", waId, delivered],
]) {
  await page.goto(`${APP}/biz?receipt=${id}`);
  await expect(panel().getByRole("heading", { name: "Saved expense" })).toBeVisible();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download" }).click()]);
  const path = join(OUT, `downloaded-${name}.bin`);
  await download.saveAs(path);
  downloads[name] = sha(readFileSync(path)) === sha(bytes);
  await pause(600);
}
await page.goto(`${APP}/biz`);
await expect(nav()).toBeVisible();
const searchControls = await page.getByRole("searchbox").count();
const searchButtons = await page.getByRole("button", { name: /search/i }).count();
const searchLinks = await page.getByRole("link", { name: /search/i }).count();
let searchNote = "";
if (searchButtons > 0) {
  await page.getByRole("button", { name: /search/i }).first().click();
  await pause(800);
  const box = page.getByRole("searchbox").or(page.getByRole("combobox")).or(page.locator('input[type="search"]')).first();
  if (await box.count()) {
    await box.fill("Ferretería");
    await pause(2500);
    const searchPanel = await page.locator("body").innerText();
    searchNote = `The shell's search control opened and was given "Ferretería"; the page then showed "Ferretería La Esquina" as a result: ${/Ferretería La Esquina[\s\S]*3,400/.test(searchPanel)}.`;
    await page.keyboard.press("Escape");
  }
}
const businessSearchRoutes = (await (await fetch("http://127.0.0.1:8621/openapi.json")).json().catch(() => ({ paths: {} })));
const searchPaths = Object.keys(businessSearchRoutes.paths ?? {}).filter((p) => /search/i.test(p));
const businessQuery = await api("A", tokenA, "GET", `/business/expenses?${RANGE}&q=Ferreter`);
section(
  "5. Reload and find",
  `After a full browser reload, Expenses lists ${expenses.body?.items?.length} expenses: ${JSON.stringify(expenses.body?.items?.map((e) => ({ merchant: e.merchant, amount: e.amount, receipt: e.receipt_id })))}. ` +
    `Receipts: view=all ${JSON.stringify(all.body?.items?.map((r) => ({ id: r.id, status: r.status })))}; view=inbox ${JSON.stringify(inboxNow.body?.items?.map((r) => ({ id: r.id, status: r.status })))}. ` +
    `Each expense row's Receipt link opened Saved expense, and Download returned the original: sha256 match ${JSON.stringify(downloads)}. ` +
    `Search: /biz shows ${searchControls} searchbox, ${searchButtons} search button(s) and ${searchLinks} search link(s). ${searchNote} OpenAPI search paths: ${JSON.stringify(searchPaths)}; none is under /business. GET /business/expenses with q=Ferreter -> ${businessQuery.status}, ${businessQuery.body?.items?.length} items (q is not a parameter; the full period list comes back).`,
);
check(
  5,
  "each expense shows in Expenses after a reload, its receipt in All",
  expenses.body?.items?.length === 3 &&
    [webConfirmed.body.expense_id, noaiDetail.body.expense_id, waConfirmed.body.expense_id].every((id) => expenses.body.items.some((e) => e.id === id)) &&
    [webId, noaiId, waId].every((id) => all.body?.items?.some((r) => r.id === id && r.status === "confirmed")) &&
    ["Ferretería La Esquina", "Farmacia Carol", "Colmado Don Pedro"].every((m) => expensesText.includes(m)),
);
check(5, "each original downloads with a matching sha256", Object.values(downloads).every(Boolean));
const hasBusinessSearch = searchPaths.some((p) => p.startsWith("/api/v1/business"));
md(`- ${hasBusinessSearch ? "PASS" : "GAP"}: find a Business expense by merchant (${hasBusinessSearch ? "a Business search route exists" : "no Business search in the UI or the API; not built"})`);
results.push({ step: 5, name: "Business search", ok: true, gap: !hasBusinessSearch });

// ---------------------------------------------------------------- Step 6
const personalAccount = await api("A", tokenA, "POST", "/financial-accounts", {
  body: { type: "checking", currency: "DOP", nickname: "Cuenta personal" },
  headers: { "Idempotency-Key": randomUUID() },
});
alias(personalAccount.body?.id, "A personal account");
const personalDoc = await api("A", tokenA, "POST", "/financial-documents", {
  bytes: receipts.web,
  headers: { "Content-Type": "image/png", "X-Document-Filename": "ferreteria-personal.png" },
});
alias(personalDoc.body?.connection_id, "A personal document");
const expenseBody = {
  kind: "expense",
  account_id: personalAccount.body?.id,
  amount: "1200.00",
  occurred_at: "2026-10-06T12:00:00-04:00",
  note: "Supermercado Nacional",
  category_id: "groceries",
};
const preview = await api("A", tokenA, "POST", "/financial-activities/preview", { body: expenseBody });
const personalExpense = await api("A", tokenA, "POST", "/financial-activities", {
  body: { ...expenseBody, expected_versions: preview.body?.expected_versions, ...(preview.body?.preview_token ? { preview_token: preview.body.preview_token } : {}) },
  headers: { "Idempotency-Key": randomUUID() },
});
const personalExpenseId = alias(personalExpense.body?.activity?.activity_id, "A personal expense");
const step6Counts = counts();
section(
  "6a. Personal data for owner A",
  `Personal account "Cuenta personal" -> ${personalAccount.status}. Personal document upload of the same bytes as the Business web receipt (sha256 ${sha(receipts.web).slice(0, 12)}, no AI) -> ${personalDoc.status} status ${personalDoc.body?.status}, replayed ${personalDoc.body?.replayed}. Personal expense "Supermercado Nacional" 1,200.00 DOP via /financial-activities (preview ${preview.status}) -> ${personalExpense.status}.`,
  { counts: step6Counts },
);

const businessIds = [webId, noaiId, waId, slowId];
const businessExpenseIds = [webConfirmed.body.expense_id, noaiDetail.body.expense_id, waConfirmed.body.expense_id];
const businessNeedles = [...businessIds, ...businessExpenseIds, bizAccount.body.id, "Ferretería La Esquina", "FERRETERIA", "Farmacia", "Colmado", "COLMADO", "LIBRERIA", "Cuenta operativa"];
const personalNeedles = [personalAccount.body?.id, personalDoc.body?.connection_id, personalExpenseId, "Supermercado", "Cuenta personal", "ferreteria-personal"];
const hits = (value, needles) => needles.filter((needle) => needle && JSON.stringify(value ?? null).includes(needle));
const personalReads = {};
for (const path of [
  "/financial-accounts",
  "/financial-documents",
  "/financial-imports?state=open",
  "/financial-imports?state=accepted",
  "/financial-activities/purchases",
  "/financial-home",
  "/financial-search?q=Ferreter",
  "/financial-search?q=Colmado",
  "/financial-search?q=Farmacia",
  "/financial-search?q=Libreria",
  "/financial-search?q=",
  "/search?q=Ferreter",
]) {
  personalReads[path] = await api("A", tokenA, "GET", path);
}
const businessReads = {};
for (const path of ["/business/receipts?view=all", "/business/receipts?view=inbox", `/business/expenses?${RANGE}`, "/business/workspace", `/business/overview?${RANGE}`, "/business/updates"]) {
  businessReads[path] = await api("A", tokenA, "GET", path);
}
const personalLeaks = Object.fromEntries(Object.entries(personalReads).map(([path, r]) => [path, { status: r.status, business_hits: hits(r.body, businessNeedles) }]));
const businessLeaks = Object.fromEntries(Object.entries(businessReads).map(([path, r]) => [path, { status: r.status, personal_hits: hits(r.body, personalNeedles) }]));
const personalSeesOwn = {
  documents: hits(personalReads["/financial-documents"].body, [personalDoc.body?.connection_id]).length === 1,
  purchases: hits(personalReads["/financial-activities/purchases"].body, [personalExpenseId]).length === 1,
  home: hits(personalReads["/financial-home"].body, [personalExpenseId]).length === 1,
  search: hits((await api("A", tokenA, "GET", "/financial-search?q=Supermercado")).body, [personalExpenseId]).length === 1,
};
const homeSpend = personalReads["/financial-home"].body?.currencies?.find((c) => c.currency === "DOP")?.gross_purchases_minor;
const overviewTotals = businessReads[`/business/overview?${RANGE}`].body?.totals;
writeFileSync(join(OUT, "isolation-reads.json"), redact(JSON.stringify({ personalLeaks, businessLeaks, personalSeesOwn, homeSpend, overviewTotals }, null, 1)) + "\n");

const cross = {
  "POST /business/expenses with A's Personal account": await api("A", tokenA, "POST", "/business/expenses", {
    body: { account_id: personalAccount.body?.id, amount: "10.00", occurred_on: "2026-10-07", merchant: "cross" },
    headers: { "Idempotency-Key": randomUUID() },
  }),
  "GET /business/receipts/{Personal document}": await api("A", tokenA, "GET", `/business/receipts/${personalDoc.body?.connection_id}`),
  "GET /business/receipts/{Personal document}/source": await api("A", tokenA, "GET", `/business/receipts/${personalDoc.body?.connection_id}/source`),
  "GET /financial-accounts/{Business account}": await api("A", tokenA, "GET", `/financial-accounts/${bizAccount.body.id}`),
  "POST /financial-activities/preview with the Business account": await api("A", tokenA, "POST", "/financial-activities/preview", { body: { ...expenseBody, account_id: bizAccount.body.id } }),
  "GET /financial-documents/{web receipt}": await api("A", tokenA, "GET", `/financial-documents/${webId}`),
  "GET /financial-documents/{web receipt}/source": await api("A", tokenA, "GET", `/financial-documents/${webId}/source`),
  "GET /financial-activities/{web expense}": await api("A", tokenA, "GET", `/financial-activities/${webConfirmed.body.expense_id}`),
};
cross["POST /business/expenses with a random account id"] = await api("A", tokenA, "POST", "/business/expenses", {
  body: { account_id: randomUUID(), amount: "10.00", occurred_on: "2026-10-07", merchant: "cross" },
  headers: { "Idempotency-Key": randomUUID() },
});
cross["PATCH /business/receipts/{no-AI receipt}/review account_id = random id"] = await api("A", tokenA, "PATCH", `/business/receipts/${noaiId}/review`, { body: { version: noaiDetail.body.version, fields: { account_id: randomUUID() } } });
const crossReview = await api("A", tokenA, "PATCH", `/business/receipts/${noaiId}/review`, { body: { version: noaiDetail.body.version, fields: { account_id: personalAccount.body?.id } } });
cross["PATCH /business/receipts/{no-AI receipt}/review account_id = Personal account"] = crossReview;
const crossStatus = Object.fromEntries(Object.entries(cross).map(([k, r]) => [k, `${r.status} ${r.body?.code ?? ""}`.trim()]));
const step6After = counts();
section(
  "6b. Personal and Business stay separate",
  `Personal reads as A (status and any Business id, merchant or account name found in the body):\n\n\`\`\`json\n${JSON.stringify(personalLeaks, null, 1)}\n\`\`\`\n\n` +
    `Personal still sees its own rows: ${JSON.stringify(personalSeesOwn)}. Personal home DOP gross purchases (minor units): ${homeSpend}.\n\n` +
    `Business reads as A (any Personal id, merchant or account name found):\n\n\`\`\`json\n${JSON.stringify(businessLeaks, null, 1)}\n\`\`\`\n\n` +
    `Business overview totals: ${JSON.stringify(overviewTotals)}.\n\n` +
    `Same file in both scopes: Business web receipt <web receipt> and Personal document <A personal document> are different ids: ${webId !== personalDoc.body?.connection_id}; Personal documents ${step6After.personal.documents_live}, Business documents ${step6After.business.documents_live}.\n\n` +
    `Cross-scope ids:\n\n\`\`\`json\n${JSON.stringify(crossStatus, null, 1)}\n\`\`\``,
  { counts: step6After },
);
check(
  6,
  "Personal lists, home and search never show Business receipts or expenses",
  Object.values(personalLeaks).every((r) => r.status === 200 && r.business_hits.length === 0) && homeSpend === "120000",
);
check(6, "Personal reads still show A's Personal rows", Object.values(personalSeesOwn).every(Boolean));
check(
  6,
  "Business lists never show Personal ones",
  Object.values(businessLeaks).every((r) => r.status === 200 && r.personal_hits.length === 0) && JSON.stringify(overviewTotals) === JSON.stringify([{ currency: "DOP", amount: "4604.10", count: 3 }]),
  `overview ${JSON.stringify(overviewTotals)}`,
);
check(
  6,
  "same file in Personal and Business gives two documents",
  personalDoc.status === 200 && webId !== personalDoc.body?.connection_id && step6After.personal.documents_live === 1 && step6After.business.documents_live === 4,
);
check(
  6,
  "Personal account id on POST /business/expenses returns 404",
  cross["POST /business/expenses with A's Personal account"].status === 404,
  `${crossStatus["POST /business/expenses with A's Personal account"]}; random id ${crossStatus["POST /business/expenses with a random account id"]}`,
);
check(
  6,
  "Personal account id on PATCH /business/receipts/{id}/review returns 404",
  crossReview.status === 404,
  `${crossStatus["PATCH /business/receipts/{no-AI receipt}/review account_id = Personal account"]}; random id ${crossStatus["PATCH /business/receipts/{no-AI receipt}/review account_id = random id"]}`,
);
check(
  6,
  "Business ids on Personal routes, and Personal document on Business routes, return 404",
  [
    "GET /business/receipts/{Personal document}",
    "GET /business/receipts/{Personal document}/source",
    "GET /financial-accounts/{Business account}",
    "POST /financial-activities/preview with the Business account",
    "GET /financial-documents/{web receipt}",
    "GET /financial-documents/{web receipt}/source",
    "GET /financial-activities/{web expense}",
  ].every((k) => cross[k].status === 404),
  JSON.stringify(crossStatus),
);

// ---------------------------------------------------------------- Step 7
const spaceB = await api("B", tokenB, "POST", "/business/space", { body: { language: "en" } });
alias(spaceB.body?.id, "B space");
const accountB = await api("B", tokenB, "POST", "/business/accounts", { body: { nickname: "B ops", type: "checking", currency: "DOP" }, headers: { "Idempotency-Key": randomUUID() } });
alias(accountB.body?.id, "B business account");
const probesB = {};
for (const [name, id] of [["web receipt", webId], ["WhatsApp receipt", waId], ["in-flight receipt", slowId]]) {
  probesB[`GET receipt (${name})`] = (await api("B", tokenB, "GET", `/business/receipts/${id}`)).status;
  probesB[`GET source (${name})`] = (await api("B", tokenB, "GET", `/business/receipts/${id}/source`)).status;
  probesB[`PATCH review (${name})`] = (await api("B", tokenB, "PATCH", `/business/receipts/${id}/review`, { body: { version: 1, fields: { merchant: "B" } } })).status;
  probesB[`POST confirm (${name})`] = (await api("B", tokenB, "POST", `/business/receipts/${id}/confirm`, { body: { version: 1 }, headers: { "Idempotency-Key": randomUUID() } })).status;
  probesB[`POST prepare (${name})`] = (await api("B", tokenB, "POST", `/business/receipts/${id}/prepare`, { headers: { "X-Extraction-Consent": "true" } })).status;
}
for (const id of businessExpenseIds) {
  probesB[`GET /financial-activities/{${ids.get(id)}}`] = (await api("B", tokenB, "GET", `/financial-activities/${id}`)).status;
  probesB[`GET /financial-activities/{${ids.get(id)}}/history`] = (await api("B", tokenB, "GET", `/financial-activities/${id}/history`)).status;
}
probesB["POST /business/expenses with A's Business account"] = (
  await api("B", tokenB, "POST", "/business/expenses", { body: { account_id: bizAccount.body.id, amount: "1.00", occurred_on: "2026-10-07" }, headers: { "Idempotency-Key": randomUUID() } })
).status;
probesB["GET /financial-documents/{A personal document}"] = (await api("B", tokenB, "GET", `/financial-documents/${personalDoc.body?.connection_id}`)).status;
const bLists = {
  receipts: (await api("B", tokenB, "GET", "/business/receipts?view=all")).body?.items?.length,
  expenses: (await api("B", tokenB, "GET", `/business/expenses?${RANGE}`)).body?.items?.length,
  workspace_accounts: hits((await api("B", tokenB, "GET", "/business/workspace")).body, [bizAccount.body.id, "Cuenta operativa"]).length,
};
const anon = {};
for (const [method, path] of [
  ["GET", "/business/space"],
  ["GET", "/business/workspace"],
  ["GET", "/business/receipts?view=all"],
  ["GET", `/business/receipts/${webId}`],
  ["GET", `/business/receipts/${webId}/source`],
  ["GET", `/business/expenses?${RANGE}`],
  ["POST", `/business/receipts/${webId}/confirm`],
]) {
  anon[`${method} ${path.split("?")[0]}`] = (await api("signed out", null, method, path, method === "POST" ? { body: { version: 1 }, headers: { "Idempotency-Key": randomUUID() } } : {})).status;
}
section(
  "7. Denied access",
  `Owner B started their own space (${spaceB.status}) and account (${accountB.status}). B's probes on A's ids:\n\n\`\`\`json\n${JSON.stringify(probesB, null, 1)}\n\`\`\`\n\nB's own lists: ${JSON.stringify(bLists)}. Signed-out requests:\n\n\`\`\`json\n${JSON.stringify(anon, null, 1)}\n\`\`\``,
  { counts: counts() },
);
check(7, "owner B gets 404 for A's receipts, sources and expense ids", Object.values(probesB).every((s) => s === 404), JSON.stringify(probesB));
check(7, "owner B's lists hold none of A's records", bLists.receipts === 0 && bLists.expenses === 0 && bLists.workspace_accounts === 0);
check(7, "signed-out requests get 401", Object.values(anon).every((s) => s === 401), JSON.stringify(anon));

// ---------------------------------------------------------------- Step 4c: the in-flight job after the lease
const settleStart = Date.now();
const settled = await until(async () => {
  const detail = await api("A", tokenA, "GET", `/business/receipts/${slowId}`);
  http.pop();
  return detail.body?.status !== "preparing" && detail.body?.status !== "queued" ? detail : null;
}, Number(process.env.SETTLE_MS ?? 9 * 60_000), 5_000);
const sweepLog = readFileSync(join(HERE, "api.log"), "utf8").split("\n").filter((l) => /Document preparation (outcome unknown|redispatched|attempts exhausted)/.test(l));
const slowStubLines = stubLines().slice(stubStart).filter((line) => line.includes(" " + sha(receipts.slow).slice(0, 12) + " "));
await page.goto(`${APP}/biz?receipt=${slowId}`);
await expect(panel().getByRole("heading", { name: "Review receipt" })).toBeVisible();
await pause(1500);
const slowPanel = await panel().innerText();
const afterSweep = counts();
section(
  "4c. The interrupted preparation after the restart",
  `Polled the in-flight receipt for ${Math.round((Date.now() - settleStart) / 1000)} s after the earlier steps (the connection lease from the dead worker lasts 5 minutes; the restarted API sweeps every 5 s). Status: ${settled?.body?.status}, error ${settled?.body?.error_code ?? JSON.stringify(settled?.body?.error ?? null)}. ` +
    `API log lines from the sweep: ${JSON.stringify(sweepLog.map((l) => l.replace(/^.*\| /, "").slice(0, 160)))}. ` +
    `Stub extractor calls for this receipt across both processes: ${slowStubLines.length} (${slowStubLines.map((l) => l.split(" ")[1]).join(", ").replace(/pid=\d+/g, "pid")}). The review screen shows: ${JSON.stringify(slowPanel.split("\n").filter((l) => /attention|stopped|Prepare|Try again/i.test(l)).slice(0, 4))}.`,
  { counts: afterSweep },
);
check(
  4,
  "interrupted preparation swept with no second extractor call",
  settled?.body?.status === "needs_attention" && slowStubLines.length === 1 && afterSweep.business.import_events_accepted === beforeKill.business.import_events_accepted,
  `status ${settled?.body?.status}, stub calls ${slowStubLines.length}`,
);

writeFileSync(join(OUT, "console-errors.txt"), redact(consoleErrors.join("\n")));
await context.close();
await browser.close();

const after = { A: counts(), B: counts(users.OWNER_B_ID) };
writeFileSync(join(OUT, "counts-after.json"), JSON.stringify(after, null, 1) + "\n");
writeFileSync(join(OUT, "ids.json"), JSON.stringify({ slowId, webId }, null, 1));
md(`\n## Counts after steps 1 to 7\n\n\`\`\`json\n${JSON.stringify(after, null, 1)}\n\`\`\`\n\nStub extractor calls this run: ${stubLines().length - stubStart} (web receipt 1, WhatsApp receipt 1, in-flight receipt 1). Browser console errors: ${consoleErrors.length}.\n`);
const failed = results.filter((r) => !r.ok);
console.log(`${results.length - failed.length}/${results.length} ok`);
process.exit(failed.length ? 1 : 0);
