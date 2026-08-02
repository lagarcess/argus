import { expect, test, type Page, type Route } from "@playwright/test";

const CONVERSATION_ID = "00000000-0000-4000-8000-000000000340";
const RUN_ID = "00000000-0000-4000-8000-000000000341";
const ARTIFACT_ID = "00000000-0000-4000-8000-000000000342";
const NOTE = "Recheck after the next inflation report.";

type LocaleFixture = {
  language: "en" | "es-419";
  search: string;
  searchPlaceholder: string;
  signIn: string;
  conversionCopy: string;
  emailPlaceholder: string;
  passwordPlaceholder: string;
  notePlaceholder: string;
  watching: string;
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function account(
  accountKind: "guest" | "registered",
  language: LocaleFixture["language"],
) {
  return {
    user: {
      id:
        accountKind === "guest"
          ? "00000000-0000-4000-8000-000000000343"
          : "00000000-0000-4000-8000-000000000344",
      email: accountKind === "guest" ? null : "owner@example.com",
      username: accountKind === "guest" ? null : "owner",
      display_name: accountKind === "guest" ? null : "Owner",
      language,
      locale: language === "es-419" ? "es-419" : "en-US",
      onboarding: {
        completed: true,
        stage: "completed",
        language_confirmed: true,
        primary_goal: null,
      },
    },
    account_kind: accountKind,
    public_account_access_enabled: true,
    ...(accountKind === "guest"
      ? {
          guest: {
            expires_at: "2026-08-03T18:00:00Z",
            conversation_limit: 1,
            message_limit: 10,
            simulation_limit: 1,
            feedback_limit: 5,
          },
        }
      : {}),
    capabilities: {
      can_create_additional_conversation: accountKind === "registered",
      can_manage_conversation: accountKind === "registered",
      can_save_decision: accountKind === "registered",
      can_manage_account: accountKind === "registered",
      can_use_omnisearch: true,
      can_search_current_workspace: true,
      can_use_grounded_discovery: false,
      can_submit_feedback: true,
    },
  };
}

function searchPayload(accountKind: "guest" | "registered") {
  return {
    items: [
      {
        type: "conversation",
        id: CONVERSATION_ID,
        title: "Gold pullback ideas",
        archived: false,
        matched_text: NOTE,
        updated_at: "2026-08-02T16:00:00Z",
        conversation_id: CONVERSATION_ID,
        match: {
          layer: "decision_note",
          fragment: NOTE,
          count: 1,
          message_id: "00000000-0000-4000-8000-000000000345",
        },
        decision_states: ["watching"],
        total_runs: 1,
        decided_runs: 1,
        dossier: {
          run_id: RUN_ID,
          run_label: "Weekly GLD pullback",
          completed_at: "2026-08-02T15:00:00Z",
          result_message_id: "00000000-0000-4000-8000-000000000345",
          tested: {
            symbols: ["GLD"],
            strategy_family: "buy_and_hold",
            cadence: "weekly",
            timeframe: "1D",
            start_date: "2025-01-01",
            end_date: "2026-08-01",
          },
          outcome: {
            run_label: "Weekly GLD pullback",
            completed_at: "2026-08-02T15:00:00Z",
            benchmark_symbol: "SPY",
            quick_take: "GLD held up better than SPY.",
            metrics: [
              { name: "total_return_pct", value: 8.4 },
              { name: "benchmark_return_pct", value: 6.1 },
              { name: "delta_vs_benchmark_pct", value: 2.3 },
            ],
          },
          decision: {
            state: "watching",
            note: NOTE,
            run_label: "Weekly GLD pullback",
          },
          actions: [
            {
              type: "decision",
              availability:
                accountKind === "guest"
                  ? "account_conversion_required"
                  : "available",
              evidence_artifact_id: ARTIFACT_ID,
              decision_state: "watching",
              note: NOTE,
              run_label: "Weekly GLD pullback",
            },
          ],
        },
      },
    ],
    ledger_groups: [],
    next_cursor: null,
  };
}

async function mockJourney(page: Page, language: LocaleFixture["language"]) {
  let accountKind: "guest" | "registered" = "guest";
  let decisionWrites = 0;
  let pendingAction: Record<string, unknown> | null = null;

  await page.route("**/api/v1/me", (route) =>
    fulfillJson(route, account(accountKind, language)),
  );
  await page.route("**/api/v1/me/usage", (route) =>
    fulfillJson(route, {
      allowances: {
        messages: { available_now: true },
        backtests: { available_now: true },
      },
    }),
  );
  await page.route("**/api/v1/conversations**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/activity")) {
      await fulfillJson(route, {
        operation: { status: "idle", kind: null, updated_at: null },
        attention: { status: "none", cursor: null },
      });
      return;
    }
    if (path.endsWith("/messages")) {
      await fulfillJson(route, {
        items: [
          {
            id: "00000000-0000-4000-8000-000000000345",
            conversation_id: CONVERSATION_ID,
            role: "assistant",
            content: "The latest GLD run is ready to review.",
            created_at: "2026-08-02T15:01:00Z",
            metadata: {},
          },
        ],
        next_cursor: null,
      });
      return;
    }
    await fulfillJson(route, {
      items: [
        {
          id: CONVERSATION_ID,
          title: "Gold pullback ideas",
          title_source: "assistant_generated",
          pinned: false,
          archived: false,
          created_at: "2026-08-02T14:00:00Z",
          updated_at: "2026-08-02T16:00:00Z",
          language: "en",
        },
      ],
      next_cursor: null,
    });
  });
  await page.route("**/api/v1/history**", (route) =>
    fulfillJson(route, { items: [], next_cursor: null }),
  );
  await page.route("**/api/v1/search**", (route) =>
    fulfillJson(route, searchPayload(accountKind)),
  );
  await page.route("**/api/v1/analytics/guest-events", (route) =>
    fulfillJson(route, { success: true }),
  );
  await page.route("**/api/v1/auth/guest/handoffs", async (route) => {
    const body = route.request().postDataJSON() as {
      pending_action?: Record<string, unknown>;
    };
    pendingAction = body.pending_action ?? null;
    await fulfillJson(route, {
      handoff_id: "00000000-0000-4000-8000-000000000346",
      expires_at: "2026-08-02T17:00:00Z",
    });
  });
  await page.route("**/api/v1/auth/login", async (route) => {
    accountKind = "registered";
    await fulfillJson(route, {
      session: null,
      user: account("registered", language).user,
      guest_claim: {
        conversation_id: CONVERSATION_ID,
        pending_action: pendingAction,
      },
    });
  });
  await page.route("**/api/v1/evidence-artifacts/*/decision", (route) => {
    decisionWrites += 1;
    return fulfillJson(route, { ok: true });
  });

  return { decisionWrites: () => decisionWrites };
}

for (const locale of [
  {
    language: "en",
    search: "Search",
    searchPlaceholder: "Search Argus...",
    signIn: "Sign in",
    conversionCopy: "Sign in to save this decision.",
    emailPlaceholder: "Email address",
    passwordPlaceholder: "Password",
    notePlaceholder: "Optional note for future you",
    watching: "Watching",
  },
  {
    language: "es-419",
    search: "Buscar",
    searchPlaceholder: "Buscar en Argus...",
    signIn: "Iniciar sesión",
    conversionCopy: "Inicia sesión para guardar esta decisión.",
    emailPlaceholder: "Correo electronico",
    passwordPlaceholder: "Contrasena",
    notePlaceholder: "Nota opcional para tu yo futuro",
    watching: "Observando",
  },
] satisfies LocaleFixture[]) {
  test(`guest dossier conversion resumes the exact preserved decision in ${locale.language}`, async ({
    page,
  }, testInfo) => {
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => consoleErrors.push(error.message));
    await page.addInitScript((language) => {
      window.localStorage.setItem("i18nextLng", language);
    }, locale.language);
    const evidence = await mockJourney(page, locale.language);
    await page.goto(`/chat?conversation=${CONVERSATION_ID}`, {
      waitUntil: "networkidle",
    });

    await page.getByRole("button", { name: locale.search }).click();
    const searchInput = page.getByPlaceholder(locale.searchPlaceholder);
    const search = page
      .locator("div.fixed.inset-0")
      .filter({ has: searchInput });
    await expect(search).toBeVisible();
    await searchInput.fill("gold");

    const dossier = search.getByText("Weekly GLD pullback", { exact: true });
    await expect(dossier).toBeVisible();
    await expect(
      search.locator('[data-dossier-metric-span="full"]'),
    ).toHaveCount(1);
    await expect(
      search.locator('[data-dossier-metric-span="full"]'),
    ).toHaveClass(/col-span-2/);

    await search.locator('[data-decision-edit="true"]').click();
    await expect(evidence.decisionWrites()).toBe(0);

    const conversion = page.getByRole("dialog", { name: locale.signIn });
    await expect(conversion).toBeVisible();
    await expect(conversion.getByText(locale.conversionCopy)).toBeVisible();
    await conversion
      .getByPlaceholder(locale.emailPlaceholder)
      .fill("owner@example.com");
    await conversion
      .getByPlaceholder(locale.passwordPlaceholder)
      .fill("test-password");
    await conversion
      .getByRole("button", { name: locale.signIn, exact: true })
      .click();

    await expect(conversion).toHaveCount(0);
    const editor = search.getByPlaceholder(locale.notePlaceholder);
    await expect(editor).toHaveValue(NOTE);
    await expect(
      search.getByRole("button", { name: locale.watching, exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(evidence.decisionWrites()).toBe(0);

    await page.screenshot({
      path: testInfo.outputPath(
        `${locale.language}-${testInfo.project.name}-resumed.png`,
      ),
      fullPage: true,
    });
    await expect(page.locator("nextjs-portal")).toHaveCount(0);
    expect(consoleErrors).toEqual([]);
  });
}
