import { expect, test, type Page } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const evidenceDirectory = join(appDirectory, "docs/evidence");
const localPython = join(appDirectory, ".venv/bin/python");
const parentPython = resolve(appDirectory, "../.venv/bin/python");
const python = process.env.CLARA_TEST_PYTHON ??
  (existsSync(localPython) ? localPython : existsSync(parentPython) ? parentPython : "python3");

let backend: ChildProcess;
let temporaryDirectory: string;
let backendOutput: string;

test.beforeEach(async ({ request }) => {
  temporaryDirectory = mkdtempSync(join(tmpdir(), "clara-browser-"));
  backendOutput = "";
  backend = spawn(python, ["-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", "8012"], {
    cwd: appDirectory,
    env: {
      ...process.env,
      CLARA_DATABASE_PATH: join(temporaryDirectory, "browser.sqlite3"),
      CLARA_LLM_API_KEY: "",
      CLARA_LLM_BASE_URL: "",
      CLARA_LLM_MODEL: "",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  backend.stdout?.on("data", (chunk: Buffer) => { backendOutput += chunk.toString(); });
  backend.stderr?.on("data", (chunk: Buffer) => { backendOutput += chunk.toString(); });
  await expect.poll(async () => {
    if (backend.exitCode !== null) throw new Error(backendOutput);
    try { return (await request.get("http://127.0.0.1:8012/api/home")).status(); }
    catch { return 0; }
  }, { timeout: 20_000 }).toBe(200);
  mkdirSync(evidenceDirectory, { recursive: true });
});

test.afterEach(async () => {
  if (backend && backend.exitCode === null) {
    const stopped = new Promise<void>((resolveStop) => backend.once("exit", () => resolveStop()));
    backend.kill("SIGTERM");
    await stopped;
  }
  if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true });
});

async function publish(page: Page, scenario: string): Promise<void> {
  await page.getByTestId("demo-scenario").selectOption(scenario);
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/demo/events") && response.request().method() === "POST");
  await page.getByTestId("publish-demo-event").click();
  const response = await responsePromise;
  expect(response.status()).toBe(202);
  const { load_id } = await response.json();
  await expect.poll(async () => {
    const home = await (await page.request.get("/api/home")).json();
    return home.source_status.load_id === load_id ? home.source_status.state : "waiting";
  }).toBe(scenario === "failure" ? "stale" : "ready");
}

for (const example of [
  { language: "es", width: 1440, height: 1050 },
  { language: "en", width: 1440, height: 1050 },
  { language: "es", width: 390, height: 844 },
] as const) {
  test(`${example.language} ${example.width}: confirm, save, unchanged check, changed notice and receipts`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width: example.width, height: example.height });
    await page.goto("/");
    if (example.language === "en") await page.getByTestId("lang-en").click();
    await expect(page.getByTestId("comparison")).toHaveCount(0);
    await page.getByTestId("demo-example").first().click();
    await page.getByTestId("send-message").click();
    await expect(page.getByTestId("confirmation")).toBeVisible();
    await expect(page.getByTestId("comparison")).toHaveCount(0);
    await page.getByTestId("confirm-comparison").click();
    await expect(page.getByTestId("comparison").first()).toBeVisible();
    await page.screenshot({ path: join(evidenceDirectory, `${example.language}-${example.width}-comparison.png`), fullPage: true, animations: "disabled" });
    await page.getByTestId("source-link").first().click();
    await expect(page.getByTestId("receipt-dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("receipt-dialog")).toHaveCount(0);
    await page.getByTestId("save-comparison").click();
    await expect.poll(async () => (await (await page.request.get("/api/home")).json()).saved.length).toBe(1);
    await publish(page, "same_winner");
    await expect(page.getByTestId("notice")).toHaveCount(0);
    await publish(page, "leader_changed");
    await expect(page.getByTestId("notice").first()).toBeVisible();
    await page.getByTestId("notice").first().getByTestId("notice-open").click();
    await expect(page.getByTestId("saved-detail")).toBeVisible();
    await page.screenshot({ path: join(evidenceDirectory, `${example.language}-${example.width}-before-after.png`), fullPage: true, animations: "disabled" });
    await page.reload();
    await expect.poll(async () => (await (await page.request.get("/api/home")).json()).saved.length).toBe(1);
    await publish(page, "failure");
    const home = await (await page.request.get("/api/home")).json();
    expect(home.source_status.dataset_id).toBeTruthy();
    expect(home.source_status.error_code).toBeTruthy();
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(hasOverflow).toBe(false);
    const visibleCopy = await page.locator("body").innerText();
    expect(visibleCopy).not.toMatch(/asesor de inversión|investment adviser|investment advisor|—/i);
    expect(visibleCopy).toContain(example.language === "es" ? "sucursal" : "branch");
    expect(errors).toEqual([]);
  });
}

test("edited replay stays honest and the second country uses the same flow", async ({ page }) => {
  const externalRequests: string[] = [];
  page.on("request", request => {
    const host = new URL(request.url()).hostname;
    if (host !== "127.0.0.1" && host !== "localhost") externalRequests.push(request.url());
  });
  await page.goto("/");
  await page.getByTestId("lang-en").click();
  await page.getByTestId("demo-example").first().click();
  await page.getByTestId("chat-input").fill("Compare my edited amount for a different term.");
  await page.getByTestId("send-message").click();
  await expect(page.getByRole("alert")).toContainText("This text needs a connected model.");
  await expect(page.getByTestId("confirmation")).toHaveCount(0);
  await expect(page.getByTestId("comparison")).toHaveCount(0);

  await page.getByRole("button", { name: "I want to compare NZD 12,000 for 365 days. Use example" }).click();
  await page.getByTestId("send-message").click();
  const confirmation = page.getByTestId("confirmation");
  await expect(confirmation.locator("select[name=country]")).toHaveValue("NZ");
  await confirmation.locator("input[name=amount]").fill("13500");
  await page.getByTestId("confirm-comparison").click();
  await expect(page.getByTestId("comparison")).toContainText("NZD");
  await expect(page.getByTestId("comparison")).not.toContainText("DOP");
  await page.getByTestId("save-comparison").click();
  await expect.poll(async () => {
    const home = await (await page.request.get("/api/home")).json();
    return home.saved[0]?.baseline.inputs;
  }).toMatchObject({ country: "NZ", currency: "NZD", amount: "13500.00" });
  await page.reload();
  await expect(page.getByTestId("lang-en")).toHaveAttribute("aria-pressed", "true");
  expect(externalRequests).toEqual([]);
});
