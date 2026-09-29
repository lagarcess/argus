import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  expect,
  test as base,
  type BrowserContext,
  type Locator,
  type Page,
  type Request,
  type TestInfo,
} from "@playwright/test";
import type { FinancialAccount } from "../lib/financial-accounts-api";

export const repositoryRoot = path.resolve(__dirname, "../..");
export const privateDirectory = path.join(repositoryRoot, "temp/web-financial-accounts-local");
export const accountPath = "/dev/financial-accounts";
export const productionURL = "http://127.0.0.1:60419";
const evidenceRelative = "docs/reports/evidence/web-financial-accounts";

export interface LocalUser {
  label: "A" | "B";
  email: string;
  password: string;
  id: string;
  language: "en" | "es-419";
}
export interface LocalConfiguration {
  projectId: string;
  repositoryRoot: string;
  configuredHead: string;
  migrationSourceHead: string;
  appURL: string;
  apiURL: string;
  supabaseURL: string;
  users: LocalUser[];
}
export interface RuntimeReceipt {
  action: "api" | "web";
  pid: number;
  port: number;
  repositoryRoot: string;
  head: string;
  configuredHead: string;
  migrationSourceHead: string;
  projectId: string;
  startedAt: string;
  financialAccountsEnabled?: boolean;
  productionCheck?: boolean;
}
export interface Problem {
  code: string;
  errors?: { loc?: (string | number)[]; type?: string }[];
  context?: { errors?: { loc?: (string | number)[]; type?: string }[] };
}
export interface APIResult<T> {
  status: number;
  body: T;
}

export async function readConfiguration(): Promise<LocalConfiguration> {
  const filename = path.join(privateDirectory, "client.json");
  const permissions = await stat(filename);
  if ((permissions.mode & 0o077) !== 0) {
    throw new Error("The local account fixture must have private file permissions.");
  }
  const config = JSON.parse(await readFile(filename, "utf8")) as LocalConfiguration;
  if (
    config.projectId !== "web-accounts" ||
    config.repositoryRoot !== repositoryRoot ||
    config.appURL !== "http://127.0.0.1:3198" ||
    config.apiURL !== "http://127.0.0.1:60400/api/v1" ||
    config.supabaseURL !== "http://127.0.0.1:60401" ||
    !config.users.some((user) => user.label === "A") ||
    !config.users.some((user) => user.label === "B")
  ) {
    throw new Error("Accounts acceptance requires the owned local web-accounts stack.");
  }
  return config;
}

export function currentHead(): string {
  return execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: repositoryRoot, encoding: "utf8",
  }).trim();
}

function assertCaptureTree(expectedHead: string): void {
  if (!/^[a-f0-9]{40}$/.test(expectedHead) || currentHead() !== expectedHead) {
    throw new Error("Capture requires the explicitly supplied current full Git SHA.");
  }
  const changed = execFileSync("git", ["diff", "--name-only", "HEAD"], {
    cwd: repositoryRoot, encoding: "utf8",
  });
  const untracked = execFileSync("git", ["ls-files", "--others", "--exclude-standard"], {
    cwd: repositoryRoot, encoding: "utf8",
  });
  const outsideEvidence = `${changed}\n${untracked}`.split("\n").filter(Boolean)
    .some((filename) => !filename.startsWith(`${evidenceRelative}/`));
  if (outsideEvidence) throw new Error("Commit code and tests before recording Accounts evidence.");
}

export async function runtimeReceipts(): Promise<RuntimeReceipt[]> {
  const content = await readFile(path.join(privateDirectory, "runtime-receipts.jsonl"), "utf8");
  return content.trim().split("\n").filter(Boolean)
    .map((line) => JSON.parse(line) as RuntimeReceipt);
}

export async function ownedRuntime(port: number): Promise<RuntimeReceipt> {
  const receipt = (await runtimeReceipts()).filter((item) => item.port === port).at(-1);
  if (!receipt || receipt.projectId !== "web-accounts" || receipt.repositoryRoot !== repositoryRoot) {
    throw new Error("The local launch command has no matching process receipt.");
  }
  try { process.kill(receipt.pid, 0); } catch {
    throw new Error("The recorded local process is no longer running.");
  }
  return receipt;
}

export async function protectLocalNetwork(context: BrowserContext, config: LocalConfiguration): Promise<() => number> {
  let denied = 0;
  const origins = new Set([config.appURL, new URL(config.apiURL).origin, config.supabaseURL, productionURL]);
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const allowedWrite = url.origin !== new URL(config.apiURL).origin ||
      ["GET", "HEAD", "OPTIONS"].includes(request.method()) ||
      /^\/api\/v1\/(auth\/(login|logout|refresh|session|guest)|financial-accounts(?:\/[^/]+(?:\/opening)?)?|me)$/.test(url.pathname);
    if (!origins.has(url.origin) || !allowedWrite) {
      denied += 1;
      await route.abort("blockedbyclient");
      return;
    }
    await route.fallback();
  });
  await context.routeWebSocket("**/*", (socket) => {
    const url = new URL(socket.url());
    url.protocol = url.protocol === "wss:" ? "https:" : "http:";
    if (!origins.has(url.origin)) {
      denied += 1;
      socket.close();
    } else {
      socket.connectToServer();
    }
  });
  return () => denied;
}

// Tokens are observed from the application's own authenticated requests. They
// remain in this closure: no second login client, cookie parser, or token file.
export class LocalSession {
  private authorization = "";
  constructor(readonly page: Page, readonly config: LocalConfiguration) {
    page.on("request", (request) => {
      if (!request.url().startsWith(`${config.apiURL}/`)) return;
      const authorization = request.headers().authorization;
      if (authorization?.startsWith("Bearer ")) this.authorization = authorization;
    });
  }

  async login(label: LocalUser["label"] = "A", allowUnavailable = false): Promise<void> {
    const user = this.config.users.find((candidate) => candidate.label === label);
    if (!user) throw new Error("The local fixture is missing the requested user.");
    await this.page.goto(accountPath);
    try {
      await this.page.locator('input[type="email"]').fill(user.email);
      await this.page.locator('input[type="password"]').fill(user.password);
      await this.page.locator('form button[type="submit"]').click();
      await expect(this.page.locator('input[type="password"]')).toHaveCount(0);
    } catch {
      // Do not let Playwright's input action log echo local credentials.
      throw new Error("Sign-in through the existing AuthForm did not complete.");
    }
    await expect.poll(() => Boolean(this.authorization), { message: "Application has an authenticated session" }).toBe(true);
    if (!allowUnavailable) await expect(this.page.getByTestId("accounts-list")).toBeVisible();
  }

  async request<T = FinancialAccount>(method: string, endpoint: string, body?: unknown, key?: string): Promise<APIResult<T>> {
    if (!/^\/financial-accounts(?:\/[^/?#]+(?:\/opening)?)?$/.test(endpoint)) {
      throw new Error("Controlled API requests are restricted to local financial accounts.");
    }
    if (!this.authorization) throw new Error("Sign in through the UI before making an authenticated check.");
    const response = await fetch(`${this.config.apiURL}${endpoint}`, {
      method, redirect: "error",
      headers: {
        Authorization: this.authorization,
        "Content-Type": "application/json",
        ...(key ? { "Idempotency-Key": key } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return { status: response.status, body: await response.json() as T };
  }

  async get(id: string): Promise<FinancialAccount> {
    const result = await this.request("GET", `/financial-accounts/${id}`);
    expect(result.status).toBe(200);
    return result.body;
  }

  async list(): Promise<FinancialAccount[]> {
    const result = await this.request<{ accounts: FinancialAccount[] }>("GET", "/financial-accounts");
    expect(result.status).toBe(200);
    return result.body.accounts;
  }
}

export const labels = {
  add: /^(Add account|Agregar cuenta)$/,
  edit: /^(Edit details|Editar detalles)$/,
  saveEdit: /^(Save changes|Guardar cambios)$/,
  addOpening: /^(Add starting balance|Agregar saldo inicial)$/,
  correctOpening: /^(Correct starting balance|Corregir saldo inicial)$/,
  saveOpening: /^(Save starting balance|Guardar saldo inicial)$/,
  saveCorrection: /^(Save correction|Guardar corrección)$/,
  signOut: /^(Sign out|Cerrar sesión)$/,
} as const;

export function nickname(prefix: string): string {
  return `${prefix} ${randomUUID().slice(0, 8)}`;
}

export function financialResponse(page: Page, config: LocalConfiguration, method: string, endpoint: string) {
  return page.waitForResponse((response) => response.url() === `${config.apiURL}${endpoint}` && response.request().method() === method);
}

export async function openCreate(page: Page): Promise<Locator> {
  await page.getByRole("button", { name: labels.add, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  return dialog;
}

export async function fillCreate(dialog: Locator, input: { nickname: string; type?: string; currency?: string; amount?: string }): Promise<void> {
  await dialog.getByLabel(/^(Type|Tipo)$/).selectOption(input.type ?? "checking");
  await dialog.getByLabel(/^(Currency|Moneda)$/).selectOption(input.currency ?? "DOP");
  await dialog.getByLabel(/^(Nickname \(optional\)|Nombre \(opcional\)|Apodo \(opcional\))$/).fill(input.nickname);
  if (input.amount !== undefined) {
    await dialog.getByLabel(/^(Starting balance \(optional\)|Amount owed \(optional\)|Saldo inicial \(opcional\)|Monto adeudado \(opcional\))$/).fill(input.amount);
  }
}

export async function createAccount(session: LocalSession, input: Parameters<typeof fillCreate>[1]): Promise<FinancialAccount> {
  const dialog = await openCreate(session.page);
  await fillCreate(dialog, input);
  const responsePromise = financialResponse(session.page, session.config, "POST", "/financial-accounts");
  await dialog.getByRole("button", { name: labels.add }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(201);
  const account = await response.json() as FinancialAccount;
  await expect(dialog).toHaveCount(0);
  await expect(session.page.getByTestId("account-detail")).toBeVisible();
  return account;
}

export async function reopen(session: LocalSession, account: FinancialAccount): Promise<void> {
  await session.page.goto(`${accountPath}?account=${account.id}`);
  await expect(session.page.getByTestId("account-detail")).toBeVisible();
}

export async function submitEdit(session: LocalSession, dialog: Locator, account: FinancialAccount): Promise<FinancialAccount> {
  const pending = financialResponse(session.page, session.config, "PATCH", `/financial-accounts/${account.id}`);
  await dialog.getByRole("button", { name: labels.saveEdit }).click();
  const response = await pending;
  expect(response.status()).toBe(200);
  await expect(dialog).toHaveCount(0);
  return response.json() as Promise<FinancialAccount>;
}

export async function captureEvidence(page: Page, info: TestInfo, config: LocalConfiguration, checks: string[], details: Record<string, string | number | boolean> = {}): Promise<void> {
  if (process.env.ARGUS_ACCOUNTS_CAPTURE !== "1") return;
  const head = process.env.ARGUS_ACCOUNTS_EXPECT_HEAD ?? "";
  assertCaptureTree(head);
  const app = new URL(page.url()).origin;
  const web = await ownedRuntime(Number(new URL(app).port));
  const api = await ownedRuntime(60400);
  if (web.head !== head) throw new Error("The browser origin was not launched at the accepted code head.");
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  const directory = path.resolve(repositoryRoot, process.env.ARGUS_ACCOUNTS_EVIDENCE_DIR ?? evidenceRelative);
  const allowed = path.join(repositoryRoot, evidenceRelative);
  if (directory !== allowed && !directory.startsWith(`${allowed}${path.sep}`)) {
    throw new Error("Evidence output must stay in the financial accounts evidence directory.");
  }
  await mkdir(directory, { recursive: true });
  const slug = info.title.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase();
  const pending = path.join(directory, `.${slug}.pending.png`);
  const screenshot = path.join(directory, `${slug}.png`);
  try {
    await page.screenshot({
      path: pending, animations: "disabled", fullPage: false,
      mask: config.users.map((user) => page.getByText(user.email, { exact: false })),
    });
    assertCaptureTree(head);
    await rename(pending, screenshot);
    await writeFile(path.join(directory, `${slug}.json`), JSON.stringify({
      schemaVersion: 1, test: info.title, codeHead: head,
      capturedAt: new Date().toISOString(),
      environment: {
        project: config.projectId, app, api: config.apiURL, supabase: config.supabaseURL,
        databasePort: 60402, migrationSourceHead: config.migrationSourceHead,
        apiHead: api.head, appHead: web.head, viewport: page.viewportSize(),
      },
      checks, details, screenshot: path.basename(screenshot),
      limitations: ["Local Chromium and isolated Postgres only; no native sync claim or provider calls."],
    }, null, 2) + "\n");
    assertCaptureTree(head);
  } catch (error) {
    await rm(pending, { force: true });
    throw error;
  }
}

export function requestBody(request: Request): Record<string, unknown> {
  return request.postDataJSON() as Record<string, unknown>;
}

export const test = base.extend<{ local: LocalSession }>({
  local: [async ({ page, context }, use, info) => {
    const config = await readConfiguration();
    const head = process.env.ARGUS_ACCOUNTS_EXPECT_HEAD ?? "";
    if (process.env.ARGUS_ACCOUNTS_CAPTURE === "1") assertCaptureTree(head);
    const denied = await protectLocalNetwork(context, config);
    await use(new LocalSession(page, config));
    expect(denied(), "No external requests or provider-triggering API writes").toBe(0);
    if (process.env.ARGUS_ACCOUNTS_CAPTURE === "1") assertCaptureTree(head);
    // No trace, automatic screenshot, or storage-state artifact can contain a session.
    expect(info.attachments).toHaveLength(0);
  }, { auto: true }],
});

export { expect };
