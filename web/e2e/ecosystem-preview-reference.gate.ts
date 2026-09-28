import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import en from "../public/locales/en/common.json";
import { LANGUAGE_STORAGE_KEY, THEME_STORAGE_KEY } from "../lib/browser-storage";
import { previewCodeIdentity } from "./ecosystem-preview-evidence";
import { CONVERSATIONS, FREEZE_CSS, installBreakpointFixture } from "./support/breakpoint-fixture";

const repositoryRoot = path.resolve(__dirname, "../..");
const durableDirectory = process.env.ARGUS_PREVIEW_EVIDENCE_DIR;
const outputDirectory = path.resolve(durableDirectory ?? path.join(__dirname, "../temp/ecosystem-preview-reference"));
const productionSourceSha = "a9286b21886eb03df7a21f2f4b7d5e79af570679";
const integrationSha = "c3b2042b9b69c5b75e173d145ed0020f00ccd79e";
const sourceOwners = [
  "app/chat/page.tsx", "app/layout.tsx", "app/globals.css",
  "components/chat/ChatInterface.tsx", "components/chat/EmptyChatSurface.tsx",
  "components/sidebar/ChatSidebar.tsx", "components/sidebar/SidebarHeader.tsx",
  "components/sidebar/SidebarShell.tsx", "components/sidebar/ProfileMenu.tsx",
  "components/sidebar/ProfileSettingsPanels.tsx", "components/ui/AdaptivePanel.tsx",
  "public/locales/en/common.json",
];
const widths = [1440, 834, 390];
type Reference = { name: string; origin: string; sourceSha: string; webRoot: string };
const references: Reference[] = [
  { name: "production-source", origin: "http://127.0.0.1:3200", sourceSha: productionSourceSha,
    webRoot: "/tmp/argus-web-production-reference/web" },
  { name: "integration", origin: "http://127.0.0.1:3199", sourceSha: integrationSha,
    webRoot: path.join(repositoryRoot, "web") },
];
type RequestRecord = { method: string; url: string; disposition: string };
type Audit = { requests: RequestRecord[]; violations: string[]; pageErrors: string[]; consoleErrors: string[] };

function git(...args: string[]) {
  return execFileSync("git", args, { cwd: repositoryRoot, encoding: "utf8" }).trim();
}

// This verifies named rendered owners in a local source extraction. It does
// not assert that a hosted production deployment uses this source revision.
function verifyReferenceSource(reference: Reference) {
  const owners = sourceOwners.map((owner) => {
    const expected = execFileSync("git", ["show", `${reference.sourceSha}:web/${owner}`], { cwd: repositoryRoot });
    const actual = readFileSync(path.join(reference.webRoot, owner));
    const digest = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
    const expectedSha256 = digest(expected);
    const actualSha256 = digest(actual);
    expect(actualSha256, `${reference.name} source differs: ${owner}`).toBe(expectedSha256);
    return { path: `web/${owner}`, expectedSha256, actualSha256 };
  });
  return { sourceSha: reference.sourceSha, webTree: git("rev-parse", `${reference.sourceSha}:web`),
    extractedWebRoot: reference.webRoot, verifiedOwners: owners };
}

async function guardNetwork(page: Page, origin: string, audit: Audit, fixture: boolean) {
  page.on("pageerror", (error) => audit.pageErrors.push(error.message));
  page.on("console", (message) => {
    // Locally closed development HMR sockets and intentionally denied requests
    // can emit Chromium transport errors; their dispositions are audited below.
    if (message.type() === "error" && !/ERR_BLOCKED_BY_CLIENT|WebSocket.*closed|WebSocket.*failed/.test(message.text())) {
      audit.consoleErrors.push(message.text());
    }
  });
  await page.context().routeWebSocket("**/*", (socket) => {
    const url = new URL(socket.url());
    const localHmr = url.host === new URL(origin).host && url.pathname.startsWith("/_next/");
    audit.requests.push({ method: "WEBSOCKET", url: socket.url(), disposition: "blocked-before-connect" });
    if (!localHmr) audit.violations.push(`Unexpected websocket: ${socket.url()}`);
    socket.close({ code: 1000, reason: "Reference capture forbids websocket traffic" });
  });
  // This final boundary handles every request the fixture does not fulfill.
  await page.context().route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const api = /^\/api(?:\/|$)/.test(url.pathname);
    const allowed = url.origin === origin && !api && ["GET", "HEAD"].includes(request.method());
    audit.requests.push({ method: request.method(), url: request.url(), disposition: allowed ? "local-page-or-asset" : "blocked" });
    if (allowed) return route.continue();
    audit.violations.push(`Unexpected request: ${request.method()} ${request.url()}`);
    await route.abort("blockedbyclient");
  });
  if (!fixture) return;
  await installBreakpointFixture(page, { account: "registered", language: "en", theme: "light", emptyChat: false });
  // Registered reads are a browser fixture, not an authorization assertion.
  // The shared fixture is permissive, so this outer guard permits only its
  // named read routes and the existing local read acknowledgement shape.
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const knownRead = /^\/api\/v1\/(?:me(?:\/usage)?|conversations(?:\/[^/]+(?:\/(?:activity|messages))?)?|history|search|memory\/availability|starter-prompts)$/.test(pathname);
    let readAcknowledgement = false;
    if (request.method() === "PATCH" && /^\/api\/v1\/conversations\/[^/]+\/activity$/.test(pathname)) {
      try { readAcknowledgement = request.postDataJSON()?.action === "mark_read"; } catch { /* Malformed writes are blocked. */ }
    }
    const allowed = (request.method() === "GET" && knownRead) || readAcknowledgement;
    audit.requests.push({ method: request.method(), url: request.url(), disposition: allowed ? "locally-fulfilled-fixture" : "blocked" });
    if (allowed) return route.fallback();
    audit.violations.push(`Unexpected API request: ${request.method()} ${pathname}`);
    return route.abort("blockedbyclient");
  });
}

async function capture(page: Page, prefix: string, surface: string, captures: object[]) {
  const identity = previewCodeIdentity(repositoryRoot, durableDirectory);
  await page.evaluate(() => document.fonts.ready);
  const file = `${prefix}-${surface}.png`;
  await page.screenshot({ path: path.join(outputDirectory, file), animations: "disabled", caret: "hide", scale: "css", style: FREEZE_CSS });
  captures.push({ file, surface, url: page.url(), viewport: page.viewportSize(), codeHead: identity.codeHead,
    capturedAt: new Date().toISOString() });
}

async function runCell(page: Page, testInfo: TestInfo, name: string, origin: string, width: number,
  source: object, fixture: boolean, action: (captures: object[]) => Promise<void>) {
  const identity = previewCodeIdentity(repositoryRoot, durableDirectory);
  const audit: Audit = { requests: [], violations: [], pageErrors: [], consoleErrors: [] };
  const captures: object[] = [];
  mkdirSync(outputDirectory, { recursive: true });
  await page.setViewportSize({ width, height: 1000 });
  await guardNetwork(page, origin, audit, fixture);
  try {
    await action(captures);
    expect(audit.violations, "No unexpected network request may escape the local fixture boundary").toEqual([]);
    expect(audit.pageErrors, "Uncaught browser errors").toEqual([]);
    expect(audit.consoleErrors, "Browser console errors").toEqual([]);
    expect(previewCodeIdentity(repositoryRoot, durableDirectory).codeHead).toBe(identity.codeHead);
  } finally {
    const evidence = { name, ...identity, source, origin, captures, audit,
      environment: { browser: page.context().browser()?.version(), node: process.version, platform: os.platform(), release: os.release(),
        viewport: page.viewportSize(), deviceScaleFactor: 1, timezone: "America/Santo_Domingo", locale: "en-US",
        appearance: "light", reducedMotion: "reduce", serviceWorkers: "blocked", websockets: "blocked", retries: 0 },
      limitations: ["Local source reference, not hosted-deployment verification or founder visual approval.",
        "Registered identity and financial/chat readouts are local fixtures; no real authorization, model turn, write or provider call is exercised.",
        "Only named rendered source owners are byte-verified; the pinned full web Git tree is recorded for context.",
        "Screenshots freeze animations/caret and hide Next development chrome and the fixture DevModeBadge via shared FREEZE_CSS."],
    };
    const body = JSON.stringify(evidence, null, 2);
    writeFileSync(path.join(outputDirectory, `${name}.json`), `${body}\n`);
    await testInfo.attach("reference-capture-audit", { body, contentType: "application/json" });
  }
}

for (const reference of references) for (const width of widths) {
  test(`${reference.name}-${width}`, async ({ page }, testInfo) => {
    const name = `${reference.name}-${width}`;
    const source = verifyReferenceSource(reference);
    await runCell(page, testInfo, name, reference.origin, width, source, true, async (captures) => {
      await page.goto(`${reference.origin}/chat`, { waitUntil: "networkidle" });
      await expect(page.getByTestId("chat-input")).toBeVisible();
      await capture(page, name, width >= 720 ? "cold-chat-expanded-rail" : "cold-chat", captures);
      if (width >= 720) {
        await page.getByRole("button", { name: "Collapse sidebar", exact: true }).click();
        await expect(page.getByRole("button", { name: "Expand sidebar", exact: true })).toBeVisible();
        await capture(page, name, "cold-chat-collapsed-rail", captures);
        await page.getByRole("button", { name: "Expand sidebar", exact: true }).click();
      } else {
        await page.getByTestId("chat-shell-menu-trigger").click();
      }
      await page.getByRole("button", { name: en.common.settings, exact: true }).first().click();
      await expect(page.getByRole("button", { name: en.settings.profile.title, exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: en.settings.preferences.title, exact: true })).toBeVisible();
      await capture(page, name, "settings-open", captures);

      // Hydrate a historical transcript without pressing Send or running a model.
      await page.goto(`${reference.origin}/chat?conversation=${CONVERSATIONS[0].id}`, { waitUntil: "networkidle" });
      await expect(page.getByTestId("chat-input")).toBeVisible();
      await expect(page.getByText("$10,000", { exact: false }).first()).toBeVisible();
      await capture(page, name, "active-chat-fixture", captures);
    });
  });
}

for (const width of widths) test(`preview-before-${width}`, async ({ page }, testInfo) => {
  const name = `preview-before-${width}`;
  const origin = "http://127.0.0.1:3197";
  const identity = previewCodeIdentity(repositoryRoot, durableDirectory);
  await page.addInitScript(({ themeKey, languageKey }) => {
    window.localStorage.setItem(themeKey, "light");
    window.localStorage.setItem(languageKey, "en");
  }, { themeKey: THEME_STORAGE_KEY, languageKey: LANGUAGE_STORAGE_KEY });
  await runCell(page, testInfo, name, origin, width,
    { sourceSha: identity.codeHead, webTree: git("rev-parse", `${identity.codeHead}:web`) }, false, async (captures) => {
      for (const view of ["home", "argus", "settings"] as const) {
        await page.goto(`${origin}/dev/ecosystem?view=${view}&state=sample&audience=guest`, { waitUntil: "networkidle" });
        await expect(page.getByTestId("ecosystem-preview")).toHaveAttribute("data-preview-view", view);
        await expect(page.getByTestId("preview-main")).toBeVisible();
        await capture(page, name, view, captures);
      }
    });
});
