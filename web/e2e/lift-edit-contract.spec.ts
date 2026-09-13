import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import type { ApiMessage } from "../lib/argus-api";
import type { StrategyConfirmationPayload } from "../components/chat/types";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * These cards are emitted by the real backend interpretation/confirmation path
 * with controlled planner output. The shell and transport are fixtures: this
 * suite spends no model tokens and executes no historical simulation.
 */
const evidenceRoot = path.resolve(__dirname, "../../docs/reports/evidence/430");
const screenshotRoot = path.resolve(process.env.LIFT_EDIT_SCREENSHOT_DIR ?? path.join(evidenceRoot, "browser"));
const conversationId = "conversation-alpha";
const createdAt = "2026-09-08T12:00:00Z";
type Locale = "en" | "es-419";
type CaseName = "no_change" | "refused" | "applied" | "dca_no_change" | "dca_applied"
  | "asset_replace_append_conflict" | "asset_add_append_equivalent";
type BackendCard = StrategyConfirmationPayload & { kind: "backtest" };
type Cards = Record<Locale, Record<CaseName, BackendCard>>;

function cards(): Cards {
  return JSON.parse(readFileSync(path.join(evidenceRoot, "cards.json"), "utf8")) as Cards;
}

function bundle(locale: Locale) {
  return locale === "es-419" ? es : en;
}

function message(id: string, role: "user" | "assistant", content: string,
  metadata: Record<string, unknown> = {}): ApiMessage {
  return { id, conversation_id: conversationId, role, content, created_at: createdAt, metadata };
}

function initialCard(card: BackendCard): BackendCard {
  const initialId = `initial-${card.confirmation_id}`;
  const initial = { ...card };
  delete initial.edit_disclosure;
  return {
    ...initial,
    confirmation_id: initialId,
    actions: initial.actions?.map((action) => ({
      ...action,
      payload: { ...action.payload, confirmation_id: initialId },
    })),
  };
}

function json(route: Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
}

async function installEditFixture(page: Page, locale: Locale, before: BackendCard,
  after: BackendCard, prompt: string) {
  await installMobileShellFixture(page, { language: locale, theme: "light" });
  const requests: Record<string, unknown>[] = [];
  let transcript = [
    message("initial-user", "user", locale === "es-419" ? "Prepara esta prueba." : "Prepare this test."),
    message("initial-card", "assistant", "", { confirmation_card: before }),
  ];

  // Installed last so only these two surfaces override the shared shell.
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204 });
    if (url.pathname === `/api/v1/conversations/${conversationId}/messages`) {
      return json(route, { items: transcript, next_cursor: null });
    }
    if (url.pathname !== "/api/v1/chat/stream") return route.fallback();

    const requestBody = request.postDataJSON() as Record<string, unknown>;
    requests.push(requestBody);
    expect(requestBody.message).toBe(prompt);
    expect(requestBody.action).toBeUndefined();
    transcript = [
      transcript[0],
      message("initial-card", "assistant", "", { confirmation_card: {
        ...before, confirmation_state: "superseded", status: "updated", actions: [],
      } }),
      message("edit-request", "user", prompt),
      message("edited-card", "assistant", "", { confirmation_card: after }),
    ];
    const frames = [
      { type: "stage_start", stage: "interpret" },
      { type: "stage_start", stage: "confirm" },
      { type: "final", payload: {
        stage_outcome: "await_approval", confirmation: after, message_id: "edited-card",
      } },
    ];
    return route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join("") + "data: [DONE]\n\n",
    });
  });
  return { requests, persistedCard: () => transcript.at(-1)?.metadata?.confirmation_card };
}

function requestText(locale: Locale, scenario: CaseName, after: BackendCard): string {
  const spanish = locale === "es-419";
  if (scenario === "applied") {
    const capital = after.display_facts?.starting_capital ?? after.display_facts?.capital;
    return spanish ? `Cambia el capital inicial a ${capital}.` : `Change the starting capital to ${capital}.`;
  }
  if (scenario === "dca_applied") {
    const contribution = after.display_facts?.recurring_contribution;
    return spanish ? `Cambia el aporte a ${contribution}.` : `Change the contribution to ${contribution}.`;
  }
  if (scenario === "refused") return spanish ? "Quita TSLA de la prueba." : "Remove TSLA from the test.";
  if (scenario === "asset_replace_append_conflict") {
    return spanish ? "Reemplaza NFLX por MSFT." : "Replace NFLX with MSFT.";
  }
  if (scenario === "asset_add_append_equivalent") {
    return spanish ? "Agrega MSFT a la prueba." : "Add MSFT to the test.";
  }
  return spanish ? "Cambia las condiciones de esta prueba." : "Change the conditions of this test.";
}

function currency(value: number, locale: Locale) {
  return new Intl.NumberFormat(locale, {
    style: "currency", currency: "USD", currencyDisplay: "narrowSymbol", maximumFractionDigits: 0,
  }).format(value);
}

async function assertMoney(cardElement: Locator, card: BackendCard, locale: Locale) {
  const facts = card.display_facts;
  const contribution = facts?.recurring_contribution;
  if (typeof contribution === "number") {
    const period = facts?.contribution_period as keyof typeof en.chat.confirmation.contribution_periods;
    const phrase = `${currency(contribution, locale)} ${bundle(locale).chat.confirmation.contribution_periods[period]}`;
    await expect(cardElement).toContainText(phrase);
    expect(typeof facts?.starting_capital).toBe("number");
    await expect(cardElement.getByText(currency(facts!.starting_capital!, locale), { exact: true })).toBeVisible();
  } else {
    const amount = facts?.starting_capital ?? facts?.capital;
    expect(typeof amount).toBe("number");
    await expect(cardElement).toContainText(currency(amount!, locale));
  }
}

async function assertOutcome(page: Page, scenario: CaseName, card: BackendCard, locale: Locale) {
  const latest = page.locator("section.argus-confirmation-reveal").last();
  await latest.scrollIntoViewIfNeeded();
  await expect(latest.getByRole("button", {
    name: bundle(locale).chat.confirmation.actions.run_backtest, exact: true,
  })).toBeVisible();
  await assertMoney(latest, card, locale);
  if (scenario.startsWith("asset_")) {
    const expected = scenario === "asset_replace_append_conflict" ? ["MSFT"] : ["NFLX", "MSFT"];
    await expect(latest.locator('[data-entity-token-kind="asset"]')).toHaveText(expected);
    if (scenario === "asset_replace_append_conflict") {
      expect(card.edit_disclosure?.unapplied).toEqual([
        { op: "set", target: "asset", reason: "conflicting_edit_carriers" },
      ]);
    } else {
      expect(card.edit_disclosure).toBeFalsy();
    }
  }
  const leadIn = page.getByTestId("confirmation-edit-disclosure");
  if (scenario.endsWith("no_change")) {
    await expect(leadIn).toHaveText(bundle(locale).chat.artifact_edit_disclosure.no_change_applied);
  } else if (scenario === "refused" || scenario === "asset_replace_append_conflict") {
    const targets = bundle(locale).chat.confirmation.edit_disclosure.targets;
    const labels = [...new Set(card.edit_disclosure!.unapplied.map((entry) =>
      targets[entry.target as keyof typeof targets] ?? targets.generic))];
    await expect(leadIn).toHaveText(bundle(locale).chat.confirmation.edit_disclosure.unapplied
      .replace("{{targets}}", labels.join(", ")));
  } else {
    await expect(leadIn).toHaveCount(0);
  }
  return latest.locator("..");
}

async function captureOutcome(page: Page, outcome: Locator, name: string, mobile: boolean, locale: Locale) {
  if (!mobile) {
    await outcome.evaluate((element) => element.scrollIntoView({ block: "start" }));
    const bounds = await outcome.boundingBox();
    await page.mouse.move(bounds!.x + bounds!.width / 2, 220);
    await page.mouse.wheel(0, -120);
    await expect.poll(async () => (await outcome.boundingBox())?.y ?? 0).toBeGreaterThan(90);
    await page.mouse.move(0, 0);
    await outcome.screenshot({ path: path.join(screenshotRoot, `${name}.png`), animations: "disabled" });
    return;
  }
  // A mobile card is taller than the chat viewport. Scroll the actual surface
  // for two honest views; a tall element capture paints the fixed composer
  // over controls that were outside the screen when the image was taken.
  const disclosure = page.getByTestId("confirmation-edit-disclosure");
  await disclosure.evaluate((element) => element.scrollIntoView({ block: "start" }));
  await page.mouse.move(180, 220);
  await page.mouse.wheel(0, -110);
  await expect.poll(async () => (await disclosure.boundingBox())?.y ?? 0).toBeGreaterThan(80);
  await expect(disclosure).toBeInViewport();
  await page.screenshot({ path: path.join(screenshotRoot, `${name}.png`), animations: "disabled" });
  const run = outcome.getByRole("button", {
    name: bundle(locale).chat.confirmation.actions.run_backtest, exact: true,
  });
  await run.evaluate((element) => element.scrollIntoView({ block: "center" }));
  await expect(run).toBeInViewport();
  await run.click({ trial: true });
  await page.mouse.move(375, 85);
  await page.screenshot({ path: path.join(screenshotRoot, `${name}-controls.png`), animations: "disabled" });
}

const viewports = [
  { locale: "en" as const, name: "desktop", width: 1440, height: 1000 },
  { locale: "es-419" as const, name: "desktop", width: 1440, height: 1000 },
  { locale: "es-419" as const, name: "mobile", width: 390, height: 844 },
];

for (const viewport of viewports) {
  const scenarios: CaseName[] = viewport.name === "mobile"
    ? ["dca_no_change"]
    : ["no_change", "refused", "applied", "dca_no_change", "dca_applied",
      "asset_replace_append_conflict", "asset_add_append_equivalent"];
  for (const scenario of scenarios) {
    test(`lift edit contract ${viewport.locale} ${viewport.name} ${scenario}`, async ({ page }) => {
      test.setTimeout(60_000);
      await page.setViewportSize(viewport);
      const pageErrors: string[] = [];
      page.on("pageerror", (error) => pageErrors.push(error.message));
      const fixtures = cards()[viewport.locale];
      const after = fixtures[scenario];
      const baseline = fixtures[scenario.startsWith("dca_") ? "dca_no_change" : "no_change"];
      expect(after.kind).toBe("backtest");
      const before = initialCard(baseline);
      const prompt = requestText(viewport.locale, scenario, after);
      const fixture = await installEditFixture(page, viewport.locale, before, after, prompt);
      await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
      await expect(page.locator("section.argus-confirmation-reveal")).toHaveCount(1);
      await expect(page.getByTestId("confirmation-edit-disclosure")).toHaveCount(0);
      await assertMoney(page.locator("section.argus-confirmation-reveal"), before, viewport.locale);
      if (scenario.startsWith("asset_")) {
        await expect(page.locator('section.argus-confirmation-reveal [data-entity-token-kind="asset"]'))
          .toHaveText(["NFLX"]);
      }
      await page.getByTestId("chat-input").fill(prompt);
      await page.getByTestId("chat-send").click();
      await expect(page.locator("section.argus-confirmation-reveal")).toHaveCount(2);
      const outcome = await assertOutcome(page, scenario, after, viewport.locale);
      expect(fixture.requests).toHaveLength(1);
      expect(fixture.persistedCard()).toMatchObject({ kind: "backtest" });
      if (scenario === "applied") {
        expect(after.display_facts?.capital).not.toEqual(before.display_facts?.capital);
      } else if (scenario === "dca_applied") {
        expect(after.display_facts?.recurring_contribution).not.toEqual(before.display_facts?.recurring_contribution);
        expect(after.display_facts?.starting_capital).toEqual(before.display_facts?.starting_capital);
        expect(after.display_facts?.contribution_period).toEqual(before.display_facts?.contribution_period);
      } else {
        expect(after.display_facts).toEqual(before.display_facts);
      }
      mkdirSync(screenshotRoot, { recursive: true });
      const name = `${viewport.locale}-${viewport.name}-${scenario}`;
      await captureOutcome(page, outcome, `${name}-live`, viewport.name === "mobile", viewport.locale);

      await page.reload({ waitUntil: "networkidle" });
      await expect(page.locator("section.argus-confirmation-reveal")).toHaveCount(2);
      const reloaded = await assertOutcome(page, scenario, after, viewport.locale);
      expect(fixture.requests).toHaveLength(1);
      if (scenario === "no_change" || viewport.name === "mobile" || scenario.startsWith("asset_")) {
        await captureOutcome(page, reloaded, `${name}-reload`, viewport.name === "mobile", viewport.locale);
      }
      expect(pageErrors).toEqual([]);
    });
  }
}

test("lift edit contract unknown kind never hydrates a backtest action or guest hint", async ({ page }) => {
  await installMobileShellFixture(page, { account: "guest", language: "en", theme: "light" });
  let artifact: Record<string, unknown> = initialCard(cards().en.no_change);
  await page.route(`**/api/v1/conversations/${conversationId}/messages**`, (route) => json(route, {
    items: [message("unknown-artifact", "assistant", "This artifact response is preserved.", {
      confirmation_card: artifact,
    })], next_cursor: null,
  }));
  await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
  await expect(page.getByTestId("guest-confirmation-hint")).toBeVisible();
  await expect(page.getByTestId("guest-result-hint")).toHaveCount(0);
  artifact = { ...artifact, kind: "future_calculation" };
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("This artifact response is preserved.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("guest-confirmation-hint")).toHaveCount(0);
  await expect(page.locator("section.argus-confirmation-reveal")).toHaveCount(0);
  await expect(page.getByRole("button", { name: en.chat.confirmation.actions.run_backtest, exact: true })).toHaveCount(0);
});
