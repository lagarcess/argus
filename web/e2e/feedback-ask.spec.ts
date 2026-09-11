import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test, type Page, type Route } from "@playwright/test";

import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";

/**
 * The feedback ask in a real browser, in both workspace languages: it asks
 * after a result, a tap saves a rating that carries no conversation
 * identifiers, "tell us more" opens the existing dialog, and closing the ask
 * holds across a reload.
 *
 * FEEDBACK_ASK_LIVE_API=1 sends the tap to the real backend instead of a stub,
 * so the save is the real endpoint's. FEEDBACK_ASK_EVIDENCE_DIR keeps
 * screenshots.
 */

type Language = "en" | "es-419";

const COPY = { en: en.feedback, "es-419": es419.feedback } as const;
const CONVERSATION_ID = "feedback-ask";
const NOW = "2026-09-11T12:00:00.000Z";

const RESULT_CARD = {
  title: "AAPL Buy and Hold",
  symbols: ["AAPL"],
  strategy_label: "Buy and Hold",
  asset_class: "equity",
  date_range: {
    start: "2025-09-01",
    end: "2026-09-01",
    display: "September 1, 2025 to September 1, 2026",
  },
  status_label: "Simulation Complete",
  rows: [
    { key: "cash_value", label: "Ending value", value: "$10,000 -> $12,500" },
    { key: "total_return_pct", label: "Total return", value: "+25.0%" },
    { key: "max_drawdown_pct", label: "Worst drop", value: "-8.2%" },
  ],
  assumptions: ["No fees", "No slippage"],
  actions: [],
  benchmark_note: "Universe: AAPL. Benchmark: SPY.",
  chart: null,
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function transcript(language: Language) {
  return [
    {
      id: `${CONVERSATION_ID}-1`,
      conversation_id: CONVERSATION_ID,
      role: "user",
      content:
        language === "es-419"
          ? "Prueba comprar y mantener AAPL"
          : "Test buy and hold on AAPL",
      created_at: NOW,
      metadata: {},
    },
    {
      id: `${CONVERSATION_ID}-2`,
      conversation_id: CONVERSATION_ID,
      role: "assistant",
      content: "AAPL ended higher over the window.",
      created_at: NOW,
      metadata: {
        result_card: RESULT_CARD,
        result_run_id: `${CONVERSATION_ID}-run`,
        result_conversation_id: CONVERSATION_ID,
      },
    },
  ];
}

async function installFixture(page: Page, language: Language) {
  await page.addInitScript((lang) => {
    window.localStorage.setItem("i18nextLng", lang);
    window.localStorage.setItem("argus-theme", "light");
  }, language);

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();

    if (url.pathname.endsWith("/api/v1/feedback") && method === "POST") {
      if (process.env.FEEDBACK_ASK_LIVE_API === "1") return route.continue();
      return json(route, { success: true });
    }

    if (url.pathname.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "feedback-ask-user",
          email: "qa@example.com",
          username: "qa",
          display_name: "Feedback Ask QA",
          language,
          locale: language === "es-419" ? "es-419" : "en-US",
          onboarding: {
            completed: true,
            stage: "completed",
            language_confirmed: true,
            primary_goal: null,
          },
        },
        account_kind: "registered",
        guest: null,
        capabilities: {
          can_create_additional_conversation: true,
          can_manage_conversation: true,
          can_save_decision: true,
          can_manage_account: true,
          can_use_omnisearch: true,
          can_search_current_workspace: true,
          can_use_grounded_discovery: true,
          can_submit_feedback: true,
        },
        public_account_access_enabled: false,
      });
    }

    if (url.pathname.endsWith("/api/v1/conversations") && method === "GET") {
      return json(route, {
        items: [
          {
            id: CONVERSATION_ID,
            title: "Feedback ask",
            title_source: "user_renamed",
            pinned: false,
            archived: false,
            deleted_at: null,
            created_at: NOW,
            updated_at: NOW,
            last_message_preview: "AAPL buy and hold",
            language,
            activity: null,
          },
        ],
        next_cursor: null,
      });
    }

    if (url.pathname.endsWith(`/conversations/${CONVERSATION_ID}/messages`)) {
      return json(route, { items: transcript(language), next_cursor: null });
    }

    return json(route, {});
  });
}

async function capture(page: Page, name: string) {
  const dir = process.env.FEEDBACK_ASK_EVIDENCE_DIR;
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await page.addStyleTag({
    content:
      "nextjs-portal, [data-dev-mode-badge] { display: none !important; }",
  });
  await page.screenshot({ path: join(dir, `${name}.png`) });
}

async function openConversation(page: Page) {
  await page.goto(`/chat?conversation=${CONVERSATION_ID}`);
  await expect(
    page.getByRole("region", { name: "Hero + Delta Evidence Card" }),
  ).toBeVisible();
}

for (const language of ["en", "es-419"] as const) {
  const copy = COPY[language];

  test(`${language}: asks after a result, saves a tap, and offers the dialog`, async ({
    page,
  }) => {
    await installFixture(page, language);
    await openConversation(page);

    const ask = page.getByTestId("feedback-ask");
    await expect(ask).toBeVisible();
    await expect(ask).toContainText(copy.ask.question);
    for (const rating of ["negative", "neutral", "positive"] as const) {
      await expect(
        ask.getByRole("button", { name: copy.ask.answers[rating], exact: true }),
      ).toBeVisible();
    }
    await capture(page, `${language}-1-ask-after-result`);

    const saved = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/feedback") &&
        response.request().method() === "POST",
    );
    await ask
      .getByRole("button", { name: copy.ask.answers.positive, exact: true })
      .click();
    const response = await saved;
    expect(response.status()).toBe(200);
    const submission = response.request().postDataJSON();
    expect(submission.type).toBe("general");
    expect(submission.context).toEqual({
      source: "feedback_ask",
      surface: "chat",
      rating: "positive",
      tags: [],
      hasAttachments: false,
      attachmentCount: 0,
    });
    expect(JSON.stringify(submission)).not.toContain(CONVERSATION_ID);

    await expect(ask).toContainText(copy.ask.thanks);
    await capture(page, `${language}-2-tap-saved`);

    await ask.getByRole("button", { name: copy.ask.tell_more }).click();
    const dialog = page.getByRole("dialog", { name: copy.title });
    await expect(dialog).toBeVisible();
    const includeConversation = dialog.getByRole("checkbox", {
      name: copy.include_conversation_context,
    });
    await expect(includeConversation).toBeVisible();
    await expect(includeConversation).not.toBeChecked();
    await expect(ask).toHaveCount(0);
    await capture(page, `${language}-3-tell-us-more-dialog`);

    await page.reload();
    await expect(
      page.getByRole("region", { name: "Hero + Delta Evidence Card" }),
    ).toBeVisible();
    await expect(page.getByTestId("feedback-ask")).toHaveCount(0);
  });

  test(`${language}: a dismissal holds after a reload`, async ({ page }) => {
    await installFixture(page, language);
    await openConversation(page);

    const ask = page.getByTestId("feedback-ask");
    await expect(ask).toBeVisible();
    await ask.getByRole("button", { name: copy.ask.dismiss }).click();
    await expect(ask).toHaveCount(0);

    await page.reload();
    await expect(
      page.getByRole("region", { name: "Hero + Delta Evidence Card" }),
    ).toBeVisible();
    await expect(page.getByTestId("feedback-ask")).toHaveCount(0);
    await capture(page, `${language}-4-dismissed-after-reload`);
  });
}
