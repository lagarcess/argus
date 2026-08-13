import { expect, test, type Page, type Route } from "@playwright/test";
import dcaConfirmationCard from "../../docs/reports/evidence/455/dca-confirmation-card.json";

/**
 * Issue #455 browser evidence: the DCA edit surface shows exactly two money
 * parameters and the contribution reads as one phrase, in both languages and
 * at both widths.
 *
 * The card is not hand-written here. It is the payload the real backend
 * produced for a "$200 of Coca-Cola every month" plan, committed under
 * docs/reports/evidence/455/, so what the browser renders is backend truth.
 */

const CONVERSATION_ID = "11111111-1111-4111-8111-111111111111";
const CREATED_AT = "2026-08-13T12:00:00Z";
const OUTPUT_DIR = "../docs/reports/evidence/455/browser";

type Language = "en" | "es-419";

function conversation(language: Language) {
  return {
    id: CONVERSATION_ID,
    title: "Coca-Cola monthly",
    title_source: "user_renamed",
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
    pinned: false,
    archived: false,
    deleted_at: null,
    last_message_preview: "Ready to test recurring buys for KO.",
    language,
  };
}

function assistantMessage() {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    conversation_id: CONVERSATION_ID,
    role: "assistant",
    content: "Ready to test recurring buys for KO.",
    created_at: CREATED_AT,
    metadata: {
      confirmation_card: dcaConfirmationCard,
      confirmation_payload: {
        confirmation_id: "confirmation-455-dca",
        strategy: {
          strategy_type: "dca_accumulation",
          asset_universe: ["KO"],
          asset_class: "equity",
          cadence: "monthly",
          capital_amount: 200,
          date_range: { start: "2020-01-02", end: "2024-12-31" },
        },
      },
    },
  };
}

async function installFixture(page: Page, language: Language) {
  await page.addInitScript((detected) => {
    window.localStorage.setItem("i18nextLng", detected as string);
  }, language);

  const json = (route: Route, body: unknown) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });

  // One dispatcher rather than several globs, so route registration order
  // cannot decide which handler answers the messages request.
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "issue-455-user",
          email: "qa@example.com",
          username: "qa",
          display_name: "QA",
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

    if (path.endsWith(`/api/v1/conversations/${CONVERSATION_ID}/messages`)) {
      return json(route, { items: [assistantMessage()], next_cursor: null });
    }

    if (path.endsWith("/api/v1/conversations")) {
      if (route.request().method() === "POST") {
        return json(route, { conversation: conversation(language) });
      }
      return json(route, { items: [conversation(language)], next_cursor: null });
    }

    if (path.endsWith("/api/v1/history")) {
      return json(route, {
        items: [
          {
            type: "chat",
            id: CONVERSATION_ID,
            title: "Coca-Cola monthly",
            title_source: "user_renamed",
            subtitle: "Recurring buys for KO",
            pinned: false,
            created_at: CREATED_AT,
            conversation_id: CONVERSATION_ID,
          },
        ],
        next_cursor: null,
      });
    }

    return json(route, { items: [], next_cursor: null });
  });
}

const VIEWPORTS = [
  { name: "phone", width: 390, height: 844 },
  { name: "desktop", width: 1280, height: 900 },
] as const;

const EXPECTED = {
  en: {
    startingCapitalLabel: "Starting capital",
    contributionLabel: "Contribution",
    contributionValue: "$200 monthly",
  },
  "es-419": {
    startingCapitalLabel: "Capital inicial",
    contributionLabel: "Aporte",
    contributionValue: "$200 cada mes",
  },
} as const;

for (const language of ["en", "es-419"] as const) {
  for (const viewport of VIEWPORTS) {
    test(`DCA card shows two money fields and one contribution phrase (${language}, ${viewport.name})`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installFixture(page, language);
      await page.goto(`/chat?conversation=${CONVERSATION_ID}`);

      const card = page
        .locator("[data-confirmation-status]")
        .first()
        .locator("xpath=ancestor::section[1]");
      await expect(card).toBeVisible();
      const cardText = await card.innerText();

      const expected = EXPECTED[language];
      expect(cardText).toContain(expected.contributionValue);
      expect(cardText).toContain(expected.startingCapitalLabel);
      // The word this lane removed, in either language's spelling.
      expect(cardText.toLowerCase()).not.toContain("cadence");
      expect(cardText.toLowerCase()).not.toContain("cadencia");
      expect(cardText.toLowerCase()).not.toContain("frecuencia");

      await card.screenshot({
        path: `${OUTPUT_DIR}/card-${language}-${viewport.name}.png`,
      });

      const editMoney = page.getByTestId("edit-capital");
      await expect(editMoney).toBeVisible();
      await editMoney.click();

      const seed = page.getByTestId("direct-edit-starting-capital-input");
      const contribution = page.getByTestId("direct-edit-capital-input");
      const period = page.getByTestId("direct-edit-period-select");
      await expect(seed).toBeVisible();
      await expect(contribution).toBeVisible();
      await expect(period).toBeVisible();
      // Exactly two money parameters, seeded from typed backend facts.
      await expect(seed).toHaveValue("0");
      await expect(contribution).toHaveValue("200");
      await expect(period).toHaveValue("monthly");

      const drawer = page.getByTestId("confirmation-direct-edit-form");
      await expect(drawer.locator("input[inputmode='decimal']")).toHaveCount(2);

      await card.scrollIntoViewIfNeeded();
      await card.screenshot({
        path: `${OUTPUT_DIR}/edit-${language}-${viewport.name}.png`,
      });
    });
  }
}
