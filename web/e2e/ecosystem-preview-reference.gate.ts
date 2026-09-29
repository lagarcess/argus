import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import en from "../public/locales/en/common.json";
import { LANGUAGE_STORAGE_KEY, THEME_STORAGE_KEY } from "../lib/browser-storage";
import { previewCodeIdentity } from "./ecosystem-preview-evidence";
import { referenceManifest, referenceRepositoryRoot as repositoryRoot, type Reference } from "./ecosystem-preview-reference-manifest";
import { CONVERSATIONS, FREEZE_CSS, installBreakpointFixture } from "./support/breakpoint-fixture";

const durableDirectory = process.env.ARGUS_PREVIEW_EVIDENCE_DIR;
const outputDirectory = path.resolve(durableDirectory ?? path.join(__dirname, "../temp/ecosystem-preview-reference"));
const sourceOwners = [
  "app/chat/page.tsx", "app/layout.tsx", "app/globals.css",
  "components/chat/ChatInterface.tsx", "components/chat/EmptyChatSurface.tsx",
  "components/sidebar/ChatSidebar.tsx", "components/sidebar/SidebarHeader.tsx",
  "components/sidebar/SidebarShell.tsx", "components/sidebar/ProfileMenu.tsx",
  "components/sidebar/ProfileSettingsPanels.tsx", "components/ui/AdaptivePanel.tsx",
  "public/locales/en/common.json",
];
const widths = [1440, 834, 390];
type RequestRecord = { method: string; url: string; disposition: string };
type Audit = { requests: RequestRecord[]; violations: string[]; pageErrors: string[]; consoleErrors: string[] };

function git(...args: string[]) {
  return execFileSync("git", args, { cwd: repositoryRoot, encoding: "utf8" }).trim();
}

function extractedFiles(directory: string, prefix = ""): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isDirectory()) return extractedFiles(path.join(directory, entry.name), relative);
    if (!entry.isFile()) throw new Error(`Reference source must be a regular file: ${relative}`);
    return [relative];
  });
}

// This verifies named rendered owners in a local source extraction. It does
// not assert that a hosted production deployment uses this source revision.
function verifyReferenceSource(reference: Reference) {
  const previewRoute = "app/dev/ecosystem";
  const previewFiles = reference.kind === "preview"
    ? git("ls-tree", "-r", "--name-only", reference.sourceSha, "--", `web/${previewRoute}`).split("\n").filter(Boolean).map((file) => file.slice("web/".length))
    : [];
  if (reference.kind === "preview") {
    expect(previewFiles.length, "The current commit must contain the preview route").toBeGreaterThan(0);
    const extracted = extractedFiles(path.join(reference.webRoot, previewRoute), previewRoute).sort();
    expect(extracted, "The extracted preview route must have exactly the committed source files").toEqual([...previewFiles].sort());
  }
  const owners = [...sourceOwners, ...previewFiles].map((owner) => {
    const expected = execFileSync("git", ["show", `${reference.sourceSha}:web/${owner}`], { cwd: repositoryRoot });
    const actual = readFileSync(path.join(reference.webRoot, owner));
    const digest = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
    const expectedSha256 = digest(expected);
    const actualSha256 = digest(actual);
    expect(actualSha256, `${reference.name} source differs: ${owner}`).toBe(expectedSha256);
    return { path: `web/${owner}`, expectedSha256, actualSha256 };
  });
  return { sourceSha: reference.sourceSha, webTree: git("rev-parse", `${reference.sourceSha}:web`),
    extractedWebRoot: reference.webRoot, verifiedOwners: owners, completePreviewRoute: reference.kind === "preview" };
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
    audit.requests.push({ method: "WEBSOCKET", url: socket.url(), disposition: localHmr ? "local-development-hmr" : "blocked-before-connect" });
    if (localHmr) return void socket.connectToServer();
    audit.violations.push(`Unexpected websocket: ${socket.url()}`);
    socket.close({ code: 1000, reason: "Reference capture forbids application websocket traffic" });
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

async function runCell(page: Page, testInfo: TestInfo, reference: Reference, width: number,
  action: (captures: object[]) => Promise<void>) {
  const { origin } = reference;
  const name = `${reference.name}-${width}`;
  const source = verifyReferenceSource(reference);
  const identity = previewCodeIdentity(repositoryRoot, durableDirectory);
  const audit: Audit = { requests: [], violations: [], pageErrors: [], consoleErrors: [] };
  const captures: object[] = [];
  mkdirSync(outputDirectory, { recursive: true });
  await page.setViewportSize({ width, height: 1000 });
  await guardNetwork(page, origin, audit, reference.kind === "chat");
  try {
    await action(captures);
    expect(audit.violations, "No unexpected network request may escape the local fixture boundary").toEqual([]);
    expect(audit.pageErrors, "Uncaught browser errors").toEqual([]);
    expect(audit.consoleErrors, "Browser console errors").toEqual([]);
    expect(previewCodeIdentity(repositoryRoot, durableDirectory).codeHead).toBe(identity.codeHead);
  } finally {
    const evidence = { name, ...identity, source, origin,
      server: { lifecycle: "Playwright webServer", ...reference.webServer }, captures, audit,
      environment: { browser: page.context().browser()?.version(), node: process.version, platform: os.platform(), release: os.release(),
        viewport: page.viewportSize(), deviceScaleFactor: 1, timezone: "America/Santo_Domingo", locale: "en-US",
        appearance: "light", reducedMotion: "reduce", serviceWorkers: "blocked", websockets: "only same-origin Next development HMR", retries: 0 },
      limitations: ["Local source reference, not hosted-deployment verification or founder visual approval.",
        "Registered identity and financial/chat readouts are local fixtures; no real authorization, model turn, write or provider call is exercised.",
        "Named shared rendered owners are byte-verified; current preview also verifies its complete route source file set. Other web files are not byte-verified; the full web Git tree is recorded for context.",
        "Screenshots freeze animations/caret and hide Next development chrome and the fixture DevModeBadge via shared FREEZE_CSS."],
    };
    const body = JSON.stringify(evidence, null, 2);
    writeFileSync(path.join(outputDirectory, `${name}.json`), `${body}\n`);
    await testInfo.attach("reference-capture-audit", { body, contentType: "application/json" });
  }
}

for (const reference of referenceManifest.filter((item) => item.kind === "chat")) for (const width of widths) {
  test(`${reference.name}-${width}`, async ({ page }, testInfo) => {
    const name = `${reference.name}-${width}`;
    await runCell(page, testInfo, reference, width, async (captures) => {
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

for (const reference of referenceManifest.filter((item) => item.kind === "preview")) for (const width of widths) test(`${reference.name}-${width}`, async ({ page }, testInfo) => {
  const name = `${reference.name}-${width}`;
  const { origin } = reference;
  await page.addInitScript(({ themeKey, languageKey }) => {
    window.localStorage.setItem(themeKey, "light");
    window.localStorage.setItem(languageKey, "en");
  }, { themeKey: THEME_STORAGE_KEY, languageKey: LANGUAGE_STORAGE_KEY });
  await runCell(page, testInfo, reference, width, async (captures) => {
    for (const view of ["home", "argus", "settings"] as const) {
      await page.goto(`${origin}/dev/ecosystem?view=${view}&state=sample&audience=guest`, { waitUntil: "networkidle" });
      await expect(page.getByTestId("ecosystem-preview")).toHaveAttribute("data-preview-view", view);
      await expect(page.getByTestId("preview-main")).toBeVisible();
      await capture(page, name, view, captures);
    }
  });
});
