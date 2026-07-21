import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";

export const ROOT = path.resolve(__dirname, "../../..");
export const EVIDENCE_DIR = path.join(ROOT, "temp", "qa-evidence-248");
export const SHOTS_DIR = path.join(EVIDENCE_DIR, "shots");
export const MAILPIT_URL = process.env.QA_MAILPIT_URL ?? "http://127.0.0.1:54334";
export const ARGUS_API = process.env.QA_ARGUS_API ?? "http://localhost:8000/api/v1";
export const HOSTED_MODE = Boolean(process.env.ARGUS_QA_APPROVED_SUPABASE_REF);

const IDENTITY_FILE = path.join(ROOT, ".qa-identities.env");
const STATE_FILE = path.join(EVIDENCE_DIR, "qa-state.json");

function parseEnvFile(file: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of readFileSync(file, "utf8").split("\n")) {
    const match = /^([A-Z_0-9]+)=(.*)$/.exec(line.trim());
    if (match) out[match[1]] = match[2];
  }
  return out;
}

export function identities() {
  const env = parseEnvFile(IDENTITY_FILE);
  const required = [
    "QA_RECOVERY_EMAIL",
    "QA_RECOVERY_PASSWORD",
    "QA_SECOND_EMAIL",
    "QA_SECOND_PASSWORD",
  ] as const;
  for (const key of required) {
    if (!env[key]) throw new Error(`${key} missing from .qa-identities.env`);
  }
  return {
    recoveryEmail: env.QA_RECOVERY_EMAIL,
    recoveryPassword: env.QA_RECOVERY_PASSWORD,
    secondEmail: env.QA_SECOND_EMAIL,
    secondPassword: env.QA_SECOND_PASSWORD,
  };
}

type QaState = { currentPassword?: string; usedRecoveryLink?: string };

export function qaState(): QaState {
  if (!existsSync(STATE_FILE)) return {};
  return JSON.parse(readFileSync(STATE_FILE, "utf8")) as QaState;
}

export function saveQaState(patch: QaState) {
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  writeFileSync(STATE_FILE, JSON.stringify({ ...qaState(), ...patch }, null, 2));
}

export function currentRecoveryPassword(): string {
  return qaState().currentPassword ?? identities().recoveryPassword;
}

export async function screenshot(page: Page, name: string) {
  mkdirSync(SHOTS_DIR, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS_DIR, `${name}.png`), fullPage: false });
}

// ---- Mailpit -------------------------------------------------------------

export async function mailpitClear(request: APIRequestContext) {
  await request.delete(`${MAILPIT_URL}/api/v1/messages`);
}

type MailpitSummary = {
  messages: Array<{ ID: string; To: Array<{ Address: string }>; Subject: string }>;
};

export async function mailpitMessages(request: APIRequestContext) {
  const res = await request.get(`${MAILPIT_URL}/api/v1/messages?limit=50`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()) as MailpitSummary;
}

export async function mailpitWaitForRecoveryLink(
  request: APIRequestContext,
  toEmail: string,
  timeoutMs = 20_000,
): Promise<{ link: string; subject: string }> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const summary = await mailpitMessages(request);
    const message = summary.messages.find((m) =>
      m.To.some((to) => to.Address.toLowerCase() === toEmail.toLowerCase()),
    );
    if (message) {
      const res = await request.get(`${MAILPIT_URL}/api/v1/message/${message.ID}`);
      expect(res.ok()).toBeTruthy();
      const body = (await res.json()) as { HTML?: string; Text?: string };
      const haystack = `${body.HTML ?? ""}\n${body.Text ?? ""}`.replace(/&amp;/g, "&");
      const match = /(https?:\/\/[^\s"'<>)]+\/auth\/v1\/verify[^\s"'<>)]*)/.exec(haystack);
      if (match) return { link: match[1], subject: message.Subject };
      throw new Error("recovery email found but no verify link inside it");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`no recovery email for ${toEmail} within ${timeoutMs}ms`);
}

// ---- App journeys --------------------------------------------------------

export async function loginViaUi(page: Page, email: string, password: string) {
  await page.goto("/?auth=login");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL("**/chat**", { timeout: 30_000 });
}

export async function expectLoginRejected(page: Page, email: string, password: string) {
  await page.goto("/?auth=login");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page.locator("form p")).toBeVisible({ timeout: 15_000 });
  expect(page.url()).not.toContain("/chat");
}

// The app sends both credentials on API calls: an Authorization bearer from
// the browser Supabase session (argus-api.ts apiFetch) and, in same-site
// topologies, the Argus HttpOnly cookies. The helpers below keep the two
// transports separate so each claim stays honest:
//   protectedMe / protectedMeStatus  -> BEARER-TOKEN replay
//   argusCookieNames / cookie probes -> Argus HttpOnly COOKIE path
async function supabaseAccessToken(context: BrowserContext): Promise<string | null> {
  const cookies = await context.cookies("http://localhost:3000");
  const chunks = cookies
    .filter((cookie) => /^sb-.*-auth-token(\.\d+)?$/.test(cookie.name))
    .sort((a, b) => {
      const index = (name: string) => Number(/\.(\d+)$/.exec(name)?.[1] ?? 0);
      return index(a.name) - index(b.name);
    })
    .map((cookie) => cookie.value)
    .join("");
  if (!chunks) return null;
  try {
    const raw = chunks.startsWith("base64-")
      ? Buffer.from(chunks.slice("base64-".length), "base64").toString("utf8")
      : decodeURIComponent(chunks);
    return (JSON.parse(raw) as { access_token?: string }).access_token ?? null;
  } catch {
    return null;
  }
}

export async function protectedMe(
  context: BrowserContext,
): Promise<{ status: number; code: string | null }> {
  const token = await supabaseAccessToken(context);
  const res = await context.request.get(`${ARGUS_API}/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  let code: string | null = null;
  try {
    code = ((await res.json()) as { code?: string }).code ?? null;
  } catch {
    code = null;
  }
  return { status: res.status(), code };
}

export async function protectedMeStatus(context: BrowserContext): Promise<number> {
  return (await protectedMe(context)).status;
}

export async function supabaseSessionId(context: BrowserContext): Promise<string | null> {
  const token = await supabaseAccessToken(context);
  if (!token) return null;
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(Buffer.from(payload, "base64").toString("utf8")) as {
      session_id?: string;
    };
    return claims.session_id ?? null;
  } catch {
    return null;
  }
}

// ---- Argus HttpOnly cookie transport (same-site local topology) ----------

export async function argusCookieNames(context: BrowserContext): Promise<string[]> {
  const cookies = await context.cookies(ARGUS_API);
  return cookies.map((cookie) => cookie.name).sort();
}

// In-page fetch without headers: the only credential is the HttpOnly cookie.
// Returns -1 on transient fetch failures so expect.poll can retry.
export async function cookieOnlyMeStatus(page: Page): Promise<number> {
  return page.evaluate(async (api) => {
    try {
      return (await fetch(`${api}/me`, { credentials: "include" })).status;
    } catch {
      return -1;
    }
  }, ARGUS_API);
}

// Jar replay without an Authorization header, for post-revocation checks
// that must not depend on the page still being usable.
export async function cookieReplayMeStatus(context: BrowserContext): Promise<number> {
  const res = await context.request.get(`${ARGUS_API}/me`);
  return res.status();
}

// ---- Local database truth (auth.sessions) --------------------------------

const LOCAL_DB_CONTAINER = "supabase_db_argus-qa";

// Local-spec-only: a local Supabase stack implies Docker, and psql ships in
// the db container. Returns null when unavailable so callers can skip.
export function authSessionsCount(email: string): number | null {
  try {
    const out = execFileSync(
      "docker",
      [
        "exec",
        LOCAL_DB_CONTAINER,
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-tAc",
        `select count(*) from auth.sessions s join auth.users u on u.id = s.user_id where u.email = '${email}'`,
      ],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
    );
    const count = Number(out.trim());
    return Number.isFinite(count) ? count : null;
  } catch {
    return null;
  }
}

// GoTrue enforces [auth.email].max_frequency (1s here) between sends per user;
// back-to-back QA sends for the same address must respect that window.
export async function respectSendWindow() {
  await new Promise((resolve) => setTimeout(resolve, 1_500));
}

// Run-unique client addresses keep the app's real per-IP recovery limiter
// (5 per 10 minutes) from throttling consecutive QA runs against a
// long-lived dev server. The per-email limiter is left fully intact.
const RUN_NET = `10.${100 + (Date.now() % 100)}.${process.pid % 200}`;
export function runIp(host: number): string {
  return `${RUN_NET}.${host}`;
}

export async function requestRecoveryViaUi(page: Page, email: string) {
  await page.goto("/auth/forgot-password");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('button[type="submit"]').click();
  await expect(page.locator("main").getByRole("status")).toBeVisible({ timeout: 20_000 });
}

// Context-level POST shares the browser cookie jar, so the PKCE verifier
// cookie set by the route still lands in the same context. A distinct
// forwarded-for keeps QA traffic from starving the app's per-IP limiter.
export async function requestRecoveryViaApi(
  context: BrowserContext,
  email: string,
  forwardedFor?: string,
) {
  return context.request.post("http://localhost:3000/api/auth/recovery", {
    data: { email },
    headers: {
      "Content-Type": "application/json",
      Origin: "http://localhost:3000",
      ...(forwardedFor ? { "x-forwarded-for": forwardedFor } : {}),
    },
  });
}

