import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

/**
 * #509: a Spanish workspace read a Spanish card and copied English, because
 * the clipboard text was rebuilt from the backend payload instead of the view
 * model the card renders. The proof has to be a browser: the defect is
 * invisible to assertions on the payload.
 *
 * Cards here carry the shape the backend really emits, English `label`
 * strings alongside the typed `key`/`labelKey` the frontend localizes.
 */

const CONVERSATION_ID = "issue-509";
const NOW = "2026-08-18T12:00:00.000Z";

const CONFIRMATION_CARD = {
  confirmation_id: "issue-509-confirmation",
  confirmation_state: "active",
  status: "ready_to_run",
  statusLabel: "Ready to run",
  title: "AAPL Buy and Hold",
  summary: "Ready to test buy-and-hold for AAPL over the last year.",
  strategy_type: "buy_and_hold",
  asset_class: "equity",
  date_range: {
    start: "2025-08-01",
    end: "2026-08-01",
    display: "August 1, 2025 to August 1, 2026",
  },
  rows: [
    {
      key: "assets",
      label: "Assets",
      labelKey: "chat.confirmation.rows.assets",
      value: "AAPL",
    },
    {
      key: "strategy",
      label: "Strategy",
      labelKey: "chat.confirmation.rows.strategy",
      value: "Buy and Hold",
    },
    {
      key: "period",
      label: "Period",
      labelKey: "chat.confirmation.rows.period",
      value: "August 1, 2025 to August 1, 2026",
    },
    {
      key: "starting_capital",
      label: "Starting capital",
      labelKey: "chat.confirmation.rows.starting_capital",
      value: "$10,000",
    },
  ],
  assumptions: ["No fees", "No slippage"],
  actions: [],
};

const RESULT_CARD = {
  title: "AAPL Buy and Hold",
  symbols: ["AAPL"],
  strategy_label: "Buy and Hold",
  asset_class: "equity",
  date_range: {
    start: "2025-08-01",
    end: "2026-08-01",
    display: "August 1, 2025 to August 1, 2026",
  },
  status_label: "Simulation Complete",
  rows: [
    { key: "cash_value", label: "Ending value", value: "$10,000 -> $12,500" },
    { key: "total_return_pct", label: "Total return", value: "+25.0%" },
    {
      key: "benchmark_delta",
      label: "Vs benchmark",
      value: "Beat SPY by 6.0 percentage points",
    },
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

function messages() {
  return [
    {
      id: `${CONVERSATION_ID}-1`,
      conversation_id: CONVERSATION_ID,
      role: "user",
      content: "Test buy and hold on AAPL",
      created_at: NOW,
      metadata: {},
    },
    {
      id: `${CONVERSATION_ID}-2`,
      conversation_id: CONVERSATION_ID,
      role: "assistant",
      content: "",
      created_at: NOW,
      metadata: { confirmation_card: CONFIRMATION_CARD },
    },
    {
      id: `${CONVERSATION_ID}-3`,
      conversation_id: CONVERSATION_ID,
      role: "assistant",
      content: "AAPL ended higher over the window.",
      created_at: NOW,
      metadata: {
        result_card: RESULT_CARD,
        result_run_id: "issue-509-run",
        result_conversation_id: CONVERSATION_ID,
      },
    },
  ];
}

async function installFixture(page: Page, language: "en" | "es-419") {
  await page.addInitScript((lang) => {
    window.localStorage.setItem("i18nextLng", lang);
    window.localStorage.setItem("argus-theme", "light");
  }, language);

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();

    if (url.pathname.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "issue-509-user",
          email: "qa@example.com",
          username: "qa",
          display_name: "Issue 509 QA",
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
            title: "Issue 509",
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

    if (url.pathname.endsWith("/api/v1/history") && method === "GET") {
      return json(route, {
        items: [
          {
            type: "chat",
            id: CONVERSATION_ID,
            title: "Issue 509",
            title_source: "user_renamed",
            subtitle: "AAPL buy and hold",
            pinned: false,
            created_at: NOW,
            conversation_id: CONVERSATION_ID,
          },
        ],
        next_cursor: null,
      });
    }

    if (url.pathname.endsWith(`/conversations/${CONVERSATION_ID}/messages`)) {
      return json(route, { items: messages(), next_cursor: null });
    }

    return json(route, {});
  });
}

/**
 * Reads what Copy actually put on the system clipboard.
 *
 * The click is dispatched rather than driven by pointer coordinates: the Copy
 * control is hover-revealed and the transcript keeps itself scrolled to the
 * newest turn, so a positional click lands outside the viewport. The React
 * handler, the component, and the browser clipboard are all the real ones.
 */
async function copyTextFor(page: Page, cardIndex: number, copyLabel: string) {
  const sentinel = `pending-${cardIndex}`;
  await page.evaluate(
    (value) => navigator.clipboard.writeText(value),
    sentinel,
  );
  await page
    .getByRole("button", { name: copyLabel })
    .nth(cardIndex)
    .dispatchEvent("click");
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .not.toBe(sentinel);
  return page.evaluate(() => navigator.clipboard.readText());
}

/** Every `label: value` pair the card actually paints, read from the DOM. */
async function paintedRowText(card: Locator) {
  return card.evaluate((node) =>
    [...node.querySelectorAll("dt")]
      .map((term) => {
        const value = term.parentElement?.querySelector("dd");
        const label = term.textContent?.trim() ?? "";
        const painted = value?.textContent?.trim() ?? "";
        return label && painted ? `${label}: ${painted}` : "";
      })
      .filter(Boolean),
  );
}

for (const [language, copyLabel] of [
  ["es-419", "Copiar texto"],
  ["en", "Copy Plain Text"],
] as const) {
  test(`copying a card on a ${language} workspace yields ${language} text`, async ({
    page,
    context,
  }) => {
    await installFixture(page, language);
    await page.goto(`/chat?conversation=${CONVERSATION_ID}`);
    // Granting before the first navigation would scope the permission to
    // about:blank, and the clipboard would silently read back empty.
    await context.grantPermissions(["clipboard-read", "clipboard-write"], {
      origin: new URL(page.url()).origin,
    });

    await expect(
      page.locator("[data-confirmation-status]").first(),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Hero + Delta Evidence Card" }),
    ).toBeVisible();

    const confirmationCopy = await copyTextFor(page, 0, copyLabel);
    const resultCopy = await copyTextFor(page, 1, copyLabel);

    // The contract this fixes: what Copy writes is what the card paints. Every
    // label and value visible on the card has to appear in its clipboard text.
    for (const painted of await paintedRowText(
      page.locator("section.argus-confirmation-reveal"),
    )) {
      expect(confirmationCopy).toContain(painted);
    }
    for (const painted of await paintedRowText(
      page.getByRole("region", { name: "Hero + Delta Evidence Card" }),
    )) {
      expect(resultCopy).toContain(painted);
    }

    console.log(
      `\n===== ${language} CONFIRMATION CLIPBOARD =====\n${confirmationCopy}\n` +
        `===== ${language} RESULT CLIPBOARD =====\n${resultCopy}\n`,
    );

    if (language === "es-419") {
      expect(confirmationCopy).toContain("Capital inicial");
      expect(confirmationCopy).toContain("Supuestos:");
      expect(confirmationCopy).not.toContain("Starting capital");
      expect(confirmationCopy).not.toContain("Assumptions:");
      expect(confirmationCopy).not.toContain("Ready to test buy-and-hold");
      expect(resultCopy).toContain("Valor final");
      expect(resultCopy).toContain("Peor caída");
      expect(resultCopy).not.toContain("Ending value");
      expect(resultCopy).not.toContain("Worst drop");
      expect(resultCopy).not.toContain("Symbols:");
    } else {
      expect(confirmationCopy).toContain("Starting capital");
      expect(confirmationCopy).toContain("Assumptions:");
      expect(resultCopy).toContain("Ending value");
      expect(resultCopy).toContain("Worst drop");
    }
  });
}
