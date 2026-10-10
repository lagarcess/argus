import { mkdirSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { expect, test as base, type Page, type TestInfo } from "@playwright/test";
import { LANGUAGE_STORAGE_KEY, THEME_STORAGE_KEY } from "../lib/browser-storage";
import type { PreviewAudience, PreviewState, PreviewView } from "../app/dev/ecosystem/preview-content";
import { previewCodeIdentity } from "./ecosystem-preview-evidence";

export type Language = "en" | "es-419";
export type Theme = "light" | "dark" | "system";
export type View = PreviewView;
export type Audience = PreviewAudience;
export type Cell = {
  name: string;
  width: number;
  height: number;
  language: Language;
  theme: Exclude<Theme, "system">;
  captures: readonly View[];
};

type NetworkAudit = { forbidden: string[]; allowedRequests: number; pageErrors: string[] };

function forbiddenRequest(url: URL, origin: string) {
  const requestOrigin = url.origin.replace(/^ws:/, "http:").replace(/^wss:/, "https:");
  return /^\/api(?:\/|$)/.test(url.pathname)
    || (["http:", "https:", "ws:", "wss:"].includes(url.protocol) && requestOrigin !== origin);
}

export const test = base.extend<{ networkAudit: NetworkAudit }>({
  networkAudit: [async ({ context, baseURL }, use, testInfo) => {
    if (!baseURL) throw new Error("The preview network guard requires a base URL.");
    if (process.env.ARGUS_PREVIEW_EVIDENCE_DIR) codeIdentity();
    const origin = new URL(baseURL).origin;
    const startedAt = Date.now();
    const audit: NetworkAudit = { forbidden: [], allowedRequests: 0, pageErrors: [] };
    await context.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (forbiddenRequest(url, origin)) {
        audit.forbidden.push(`${request.method()} ${url.origin}${url.pathname}`);
        await route.abort("blockedbyclient");
        return;
      }
      audit.allowedRequests += 1;
      await route.continue();
    });
    await context.routeWebSocket("**/*", (socket) => {
      const url = new URL(socket.url());
      if (forbiddenRequest(url, origin)) {
        audit.forbidden.push(`WEBSOCKET ${url.origin}${url.pathname}`);
        socket.close({ code: 1008, reason: "Fixture-only preview" });
      } else socket.connectToServer();
    });
    context.on("page", (page) => {
      page.on("pageerror", (error) => audit.pageErrors.push(error.message));
    });
    await use(audit);
    await testInfo.attach("fixture-network-audit", {
      body: JSON.stringify(audit, null, 2),
      contentType: "application/json",
    });
    if (process.env.ARGUS_PREVIEW_EVIDENCE_DIR) {
      const outputDir = path.resolve(process.env.ARGUS_PREVIEW_EVIDENCE_DIR, "interactions");
      const { codeHead } = codeIdentity();
      mkdirSync(outputDir, { recursive: true });
      const name = testInfo.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
      writeFileSync(path.join(outputDir, `${name}.json`), `${JSON.stringify({
        test: testInfo.title,
        codeHead,
        recordedAt: new Date().toISOString(),
        status: audit.forbidden.length || audit.pageErrors.length ? "failed" : testInfo.status,
        elapsedMs: Date.now() - startedAt,
        browser: context.browser()?.version(),
        baseURL,
        network: audit,
        errors: testInfo.errors.map((error) => error.message),
      }, null, 2)}\n`);
    }
    expect(audit.forbidden, "The preview must not contact any API or external origin").toEqual([]);
    expect(audit.pageErrors, "The preview must not raise browser exceptions").toEqual([]);
  }, { auto: true }],
});

export { expect };

export const CELLS: readonly Cell[] = [
  { name: "desktop-en-light", width: 1440, height: 1000, language: "en", theme: "light", captures: ["home", "accounts", "argus", "plan", "search", "updates", "settings"] },
  { name: "desktop-es-dark", width: 1440, height: 1000, language: "es-419", theme: "dark", captures: ["home"] },
  { name: "tablet-en-dark", width: 834, height: 1112, language: "en", theme: "dark", captures: ["plan"] },
  { name: "tablet-es-light", width: 834, height: 1112, language: "es-419", theme: "light", captures: ["accounts"] },
  { name: "narrow-en-light", width: 390, height: 844, language: "en", theme: "light", captures: ["argus"] },
  { name: "narrow-es-dark", width: 390, height: 844, language: "es-419", theme: "dark", captures: ["home", "settings"] },
  { name: "compact-es-light", width: 360, height: 800, language: "es-419", theme: "light", captures: ["accounts"] },
];

export async function openPreview(page: Page, options: {
  view?: View;
  audience?: Audience;
  state?: PreviewState;
  language?: Language;
  theme?: Theme;
  width?: number;
  height?: number;
} = {}) {
  const { language = "en", theme = "light", view = "argus", audience = "guest", state = "sample" } = options;
  if (options.width) await page.setViewportSize({ width: options.width, height: options.height ?? 1000 });
  await page.addInitScript(({ languageKey, themeKey, language, theme }) => {
    if (localStorage.getItem(languageKey) === null) localStorage.setItem(languageKey, language);
    if (localStorage.getItem(themeKey) === null) localStorage.setItem(themeKey, theme);
  }, { languageKey: LANGUAGE_STORAGE_KEY, themeKey: THEME_STORAGE_KEY, language, theme });
  await page.emulateMedia({ colorScheme: theme === "system" ? "light" : theme, reducedMotion: "reduce" });
  const query = new URLSearchParams({ view, audience, state });
  await page.goto(`/dev/ecosystem?${query}`, { waitUntil: "networkidle" });
  await expect(page.getByTestId("ecosystem-preview")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", language);
  await expect(page.locator("html")).toHaveClass(new RegExp(`\\b${theme === "system" ? "light" : theme}\\b`));
  await page.evaluate(() => document.fonts.ready);
}

export async function controls(page: Page) {
  const details = page.getByTestId("preview-controls");
  if (!(await details.evaluate((element) => (element as HTMLDetailsElement).open))) {
    await details.locator("summary").click();
  }
  return details;
}

export async function chooseView(page: Page, view: View) {
  await controls(page);
  await page.getByTestId("preview-view").selectOption(view);
  await expect(page).toHaveURL(new RegExp(`(?:[?&])view=${view}(?:&|$)`));
}

export async function assertNoHorizontalOverflow(page: Page) {
  const geometry = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    main: (() => {
      const main = document.querySelector<HTMLElement>('[data-testid="preview-main"]');
      return main ? { scroll: main.scrollWidth, client: main.clientWidth } : null;
    })(),
  }));
  expect(geometry.document, "The document must not scroll horizontally").toBeLessThanOrEqual(geometry.viewport + 1);
  expect(geometry.body, "The body must not scroll horizontally").toBeLessThanOrEqual(geometry.viewport + 1);
  if (geometry.main) expect(geometry.main.scroll, "The reading canvas must not clip its content horizontally").toBeLessThanOrEqual(geometry.main.client + 1);
}

export async function assertFocusInsideDialog(page: Page) {
  const dialog = page.getByRole("dialog").last();
  await expect(dialog).toBeVisible();
  await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
}

export async function assertDialogFocus(page: Page) {
  const dialog = page.getByRole("dialog").last();
  await assertFocusInsideDialog(page);
  for (let index = 0; index < 12; index += 1) {
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  }
  await page.keyboard.press("Shift+Tab");
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
}

export async function assertLastControlReachable(page: Page) {
  const main = page.getByTestId("preview-main");
  const lastControl = main.locator("button:visible, a:visible, input:visible, textarea:visible, select:visible").last();
  if (await lastControl.count() === 0) return;
  await lastControl.scrollIntoViewIfNeeded();
  const geometry = await lastControl.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const x = rect.x + rect.width / 2;
    const y = rect.y + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    return { x, y, width: innerWidth, height: innerHeight, reachable: !!hit && element.contains(hit) };
  });
  expect(geometry.x).toBeGreaterThanOrEqual(0);
  expect(geometry.x).toBeLessThan(geometry.width);
  expect(geometry.y).toBeGreaterThanOrEqual(0);
  expect(geometry.y).toBeLessThan(geometry.height);
  expect(geometry.reachable, "The last control must scroll clear of fixed navigation").toBe(true);
  await main.evaluate((element) => {
    if (!(element instanceof HTMLElement)) return;
    for (let current: HTMLElement | null = element; current; current = current.parentElement) current.scrollTop = 0;
  });
}

export async function enlargeText(page: Page) {
  // Text-only enlargement, not a transform or page zoom that scales the layout
  // with its text. Snapshot computed values before applying the changes so
  // nested elements do not compound each other's new font size.
  await page.evaluate(() => {
    for (const element of document.querySelectorAll<HTMLElement>("[data-preview-text-enlarged]")) {
      const prior = JSON.parse(element.dataset.previewTextEnlarged ?? "{}") as {
        fontSize: string; fontPriority: string; lineHeight: string; linePriority: string;
      };
      element.style.setProperty("font-size", prior.fontSize, prior.fontPriority);
      element.style.setProperty("line-height", prior.lineHeight, prior.linePriority);
      delete element.dataset.previewTextEnlarged;
    }
    const elements = [...document.querySelectorAll<HTMLElement>('[data-testid="ecosystem-preview"] *, [role="dialog"] *')]
      .filter((element) => element.getClientRects().length > 0)
      .map((element) => {
        const style = getComputedStyle(element);
        return { element, fontSize: Number.parseFloat(style.fontSize), lineHeight: Number.parseFloat(style.lineHeight) };
      });
    for (const { element, fontSize, lineHeight } of elements) {
      element.dataset.previewTextEnlarged = JSON.stringify({
        fontSize: element.style.getPropertyValue("font-size"), fontPriority: element.style.getPropertyPriority("font-size"),
        lineHeight: element.style.getPropertyValue("line-height"), linePriority: element.style.getPropertyPriority("line-height"),
      });
      element.style.setProperty("font-size", `${fontSize * 2}px`, "important");
      if (Number.isFinite(lineHeight)) element.style.setProperty("line-height", `${lineHeight * 2}px`, "important");
    }
  });
}

const repositoryRoot = path.resolve(__dirname, "../..");

function codeIdentity() {
  return previewCodeIdentity(repositoryRoot, process.env.ARGUS_PREVIEW_EVIDENCE_DIR);
}

export async function capture(page: Page, testInfo: TestInfo, audit: NetworkAudit, name: string) {
  const evidenceDir = process.env.ARGUS_PREVIEW_EVIDENCE_DIR;
  const outputDir = evidenceDir ? path.resolve(evidenceDir) : testInfo.outputPath("captures");
  const { codeHead, worktreeChanges } = codeIdentity();
  mkdirSync(outputDir, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  const filename = path.join(outputDir, `${name}.png`);
  await page.screenshot({
    path: filename, fullPage: true, animations: "disabled", caret: "hide", scale: "css",
    style: "nextjs-portal { visibility: hidden !important; }",
  });
  const metadata = {
    name,
    codeHead,
    worktreeChanges: worktreeChanges || null,
    capturedAt: new Date().toISOString(),
    url: page.url(),
    viewport: page.viewportSize(),
    browser: page.context().browser()?.version(),
    platform: `${os.platform()} ${os.release()} ${os.arch()}`,
    node: process.version,
    timezone: "America/Santo_Domingo",
    reducedMotion: "reduce",
    deviceScaleFactor: 1,
    captureOnlyMask: "Next.js development indicator (nextjs-portal) hidden during screenshot capture only",
    language: await page.locator("html").getAttribute("lang"),
    resolvedTheme: await page.locator("html").getAttribute("class"),
    network: { ...audit },
    limitations: ["Local authored fixtures only", "No model, provider, authentication or financial persistence exercised"],
  };
  writeFileSync(path.join(outputDir, `${name}.json`), `${JSON.stringify(metadata, null, 2)}\n`);
  await testInfo.attach(name, { path: filename, contentType: "image/png" });
}
