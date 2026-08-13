import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import {
  BackendController,
  REPOSITORY_ROOT,
  apiJson,
  assertFreshContext,
  conversationGraph,
  deleteDisposableIdentity,
  freshGuest,
  newSignupCredentials,
  ownerSnapshot,
  profileAccountKind,
  sameGraphIds,
  workspaceFacts,
  type GuestMe,
} from "./support/guest-qa";

test.describe.configure({ mode: "serial" });

type LocaleJourney = {
  language: "en" | "es-419";
  chatInputName: string;
  newChat: string;
  createAccount: string;
  createTitle: string;
  namePlaceholder: string;
  emailPlaceholder: string;
  passwordPlaceholder: string;
  signup: string;
  checkEmail: string;
  cancel: string;
  signInTitle: string;
  signIn: string;
  runBacktest: RegExp;
  simulationComplete: RegExp;
  expectedSubject: string;
  expectedBody: string;
};

const JOURNEYS: LocaleJourney[] = [
  {
    language: "en",
    chatInputName: "Ask about any company or idea",
    newChat: "New chat",
    createAccount: "Create account",
    createTitle: "Create your account",
    namePlaceholder: "Name",
    emailPlaceholder: "Email address",
    passwordPlaceholder: "Password",
    signup: "Sign up",
    checkEmail: "Check your email",
    cancel: "Cancel",
    signInTitle: "Sign in",
    signIn: "Sign in",
    runBacktest: /Run backtest/i,
    simulationComplete: /Simulation Complete/i,
    expectedSubject: "Argus: confirm your email",
    expectedBody: "An Argus account signup was requested for",
  },
  {
    language: "es-419",
    chatInputName: "Pregunta sobre cualquier empresa o idea",
    newChat: "Nuevo chat",
    createAccount: "Crear cuenta",
    createTitle: "Crea tu cuenta",
    namePlaceholder: "Nombre",
    emailPlaceholder: "Correo electrónico",
    passwordPlaceholder: "Contraseña",
    signup: "Registrarse",
    checkEmail: "Revisa tu correo",
    cancel: "Cancelar",
    signInTitle: "Iniciar sesión",
    signIn: "Iniciar sesión",
    runBacktest: /Ejecutar backtest/i,
    simulationComplete: /Simulación completa/i,
    expectedSubject: "Argus: confirma tu correo",
    expectedBody: "Se solicitó crear una cuenta de Argus para",
  },
];

function mailpitMessage(email: string): {
  Subject: string;
  Text: string;
} {
  const mailpitUrl = process.env.ARGUS_LOCAL_MAILPIT_URL?.trim() ?? "";
  if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(mailpitUrl)) {
    throw new Error("Issue #480 browser QA requires loopback Mailpit");
  }
  const list = JSON.parse(
    execFileSync("curl", ["-fsS", `${mailpitUrl}/api/v1/messages`], {
      encoding: "utf8",
    }),
  ) as {
    messages: Array<{
      ID: string;
      To: Array<{ Address: string }>;
    }>;
  };
  const summary = list.messages.find((message) =>
    message.To.some(
      (recipient) => recipient.Address.toLowerCase() === email.toLowerCase(),
    ),
  );
  if (!summary) throw new Error("Mailpit has no signup message for the journey");
  return JSON.parse(
    execFileSync(
      "curl",
      ["-fsS", `${mailpitUrl}/api/v1/message/${summary.ID}`],
      { encoding: "utf8" },
    ),
  ) as { Subject: string; Text: string };
}

function signupConfirmationUrl(message: { Text: string }): string {
  const url = message.Text.match(/https?:\/\/[^\s)]+type=signup[^\s)]*/)?.[0];
  if (!url) throw new Error("Signup message has no confirmation URL");
  return url.replaceAll("&amp;", "&");
}

function authAuditActions(userId: string): string[] {
  if (!/^[0-9a-f-]{36}$/i.test(userId)) {
    throw new Error("Auth audit owner is invalid");
  }
  const container = process.env.ARGUS_GUEST_QA_DB_CONTAINER?.trim() ?? "";
  if (!/^supabase_db_[A-Za-z0-9_-]+$/.test(container)) {
    throw new Error("Issue #480 browser QA database container is invalid");
  }
  return execFileSync(
    "docker",
    [
      "exec",
      container,
      "psql",
      "-U",
      "postgres",
      "-d",
      "postgres",
      "-q",
      "-A",
      "-t",
      "-c",
      `select payload->>'action' from auth.audit_log_entries where payload->>'actor_id'='${userId}' or payload->'traits'->>'user_id'='${userId}' order by created_at`,
    ],
    { encoding: "utf8" },
  )
    .split("\n")
    .map((value) => value.trim())
    .filter(Boolean);
}

async function captureIssue480Evidence(
  page: Page,
  language: LocaleJourney["language"],
  state: "guest-result" | "signup-email" | "restored-result",
): Promise<void> {
  if (process.env.ARGUS_ISSUE_480_CAPTURE_EVIDENCE !== "true") return;
  const evidenceDirectory = path.join(
    REPOSITORY_ROOT,
    "docs/reports/evidence/480",
  );
  mkdirSync(evidenceDirectory, { recursive: true, mode: 0o700 });
  await page.screenshot({
    path: path.join(evidenceDirectory, `${language}-${state}.png`),
    fullPage: false,
    mask: [
      page.locator('input[type="email"]:visible'),
      page.locator('input[type="password"]:visible'),
    ],
  });
}

for (const journey of JOURNEYS) {
  test(`issue #480 ${journey.language} guest signup preserves the real result`, async ({
    page,
  }) => {
    test.setTimeout(300_000);
    const backend = new BackendController();
    const disposableUsers = new Set<string>();
    let sourceOwner = "";
    let destinationOwner = "";
    try {
      await backend.start(true);
      await assertFreshContext(page.context());
      const guest = await freshGuest(page, {
        language: journey.language,
        onBootstrapOwner(owner) {
          sourceOwner = owner;
          disposableUsers.add(owner);
        },
      });
      expect(guest.account_kind).toBe("guest");

      const conversation = await apiJson<{ conversation: { id: string } }>(
        page.context().request,
        "/conversations",
        { method: "POST", data: { language: journey.language } },
      );
      expect(conversation.status).toBe(200);
      const conversationId = conversation.body.conversation.id;

      await page.goto(`/chat?conversation=${conversationId}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("chat-input")).toHaveAccessibleName(
        journey.chatInputName,
      );
      const prompt =
        journey.language === "es-419"
          ? "Compra y mantén AAPL durante los últimos 12 meses con $10,000 y SPY como referencia."
          : "Buy and hold AAPL over the last 12 months with $10,000 and SPY as the benchmark.";
      await page.getByTestId("chat-input").fill(prompt);
      await page.getByTestId("chat-send").click();
      const runButton = page.getByRole("button", {
        name: journey.runBacktest,
      });
      await expect(runButton).toBeVisible({ timeout: 180_000 });
      await runButton.click();
      await expect(page.getByTestId("result-equity-chart")).toBeVisible({
        timeout: 240_000,
      });
      await expect(
        page.getByText(journey.simulationComplete).first(),
      ).toBeVisible();
      await expect
        .poll(() => ownerSnapshot(sourceOwner).completed_runs, {
          timeout: 60_000,
        })
        .toBe(1);
      await captureIssue480Evidence(page, journey.language, "guest-result");

      const before = conversationGraph(sourceOwner, conversationId);
      expect(before.conversation).toHaveLength(1);
      expect(before.jobs).toHaveLength(1);
      expect(before.runs).toHaveLength(1);
      expect(before.evidence.length).toBeGreaterThanOrEqual(1);

      await page.getByRole("button", { name: journey.newChat }).click();
      await page
        .getByRole("dialog", { name: /conversation|conversación/i })
        .getByRole("button", { name: journey.createAccount })
        .click();
      const signupDialog = page.getByRole("dialog", {
        name: journey.createTitle,
      });
      const credentials = newSignupCredentials();
      await signupDialog.getByPlaceholder(journey.namePlaceholder).fill("QA 480");
      await signupDialog
        .getByPlaceholder(journey.emailPlaceholder)
        .fill(credentials.email);
      await signupDialog
        .getByPlaceholder(journey.passwordPlaceholder)
        .fill(credentials.password);
      const signupResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname.endsWith("/api/v1/auth/guest/signup"),
      );
      await signupDialog
        .getByRole("button", { name: journey.signup })
        .last()
        .click();
      expect((await signupResponse).status()).toBe(200);
      await expect(
        signupDialog.getByRole("heading", { name: journey.checkEmail }),
      ).toBeVisible();
      await captureIssue480Evidence(page, journey.language, "signup-email");

      const signupMessage = mailpitMessage(credentials.email);
      expect(signupMessage.Subject).toBe(journey.expectedSubject);
      expect(signupMessage.Text).toContain(journey.expectedBody);
      expect(signupMessage.Text).toContain(credentials.email);
      expect(signupMessage.Text).not.toMatch(/\bfrom\s+to\s+|\bde\s+a\s+/i);
      const confirmation = await page.request.get(
        signupConfirmationUrl(signupMessage),
        { maxRedirects: 0 },
      );
      expect(confirmation.status()).toBe(303);

      await signupDialog
        .getByRole("button", { name: journey.cancel })
        .last()
        .click();
      await page.getByRole("button", { name: journey.signIn }).click();
      const loginDialog = page.getByRole("dialog", {
        name: journey.signInTitle,
      });
      await loginDialog
        .getByPlaceholder(journey.emailPlaceholder)
        .fill(credentials.email);
      await loginDialog
        .getByPlaceholder(journey.passwordPlaceholder)
        .fill(credentials.password);
      const loginResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname.endsWith("/api/v1/auth/login"),
      );
      await loginDialog
        .getByRole("button", { name: journey.signIn, exact: true })
        .click();
      const login = await loginResponse;
      expect(login.status()).toBe(200);
      const loginBody = (await login.json()) as {
        user: { id: string };
        guest_claim: { conversation_id: string };
      };
      destinationOwner = loginBody.user.id;
      disposableUsers.add(destinationOwner);
      expect(destinationOwner).not.toBe(sourceOwner);
      expect(loginBody.guest_claim.conversation_id).toBe(conversationId);

      const account = await apiJson<GuestMe>(page.context().request, "/me");
      expect(account.status).toBe(200);
      expect(account.body.account_kind).toBe("registered");
      expect(account.body.user.id).toBe(destinationOwner);
      expect(workspaceFacts(sourceOwner).claimed_by).toBe(destinationOwner);
      expect(profileAccountKind(sourceOwner)).toEqual({
        is_anonymous: true,
        email_present: false,
      });
      expect(
        sameGraphIds(
          before,
          conversationGraph(destinationOwner, conversationId),
        ),
      ).toBe(true);
      const sourceAfter = conversationGraph(sourceOwner, conversationId);
      expect(sourceAfter.conversation).toEqual([]);
      expect(sourceAfter.messages).toEqual([]);
      expect(sourceAfter.jobs).toEqual([]);
      expect(sourceAfter.runs).toEqual([]);
      expect(sourceAfter.evidence).toEqual([]);

      await page.goto(`/chat?conversation=${conversationId}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("result-equity-chart")).toBeVisible();
      await expect(
        page.getByText(journey.simulationComplete).first(),
      ).toBeVisible();
      await captureIssue480Evidence(page, journey.language, "restored-result");

      const auditActions = authAuditActions(destinationOwner);
      expect(auditActions).toContain("user_confirmation_requested");
      expect(auditActions).toContain("user_signedup");
      expect(auditActions).not.toContain("user_modified");
    } finally {
      await backend.stop();
      for (const userId of [...disposableUsers].reverse()) {
        await deleteDisposableIdentity(userId).catch(() => undefined);
      }
    }
  });
}
