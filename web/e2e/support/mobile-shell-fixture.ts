import type { Page, Route } from "@playwright/test";

/**
 * Deterministic chat fixture for mobile shell captures.
 *
 * Stubs the whole `/api/v1` surface so the shell renders the same conversation,
 * result card, and discovery sidecar on every run. Layout evidence must not
 * depend on a live backend or on live model output.
 */

export type FixtureAccount = "registered" | "guest";

const USER_ID = "mobile-shell-user";
const CREATED_AT = "2026-08-01T12:00:00Z";

export const CONVERSATIONS = [
  { id: "conversation-alpha", title: "Apple vs SPY, twelve months" },
  { id: "conversation-beta", title: "Weekly Nvidia buys" },
  { id: "conversation-gamma", title: "Bitcoin this year" },
  { id: "conversation-delta", title: "Monthly index contributions" },
];

const SPANISH_TITLES: Record<string, string> = {
  "conversation-alpha": "Apple frente a SPY, doce meses",
  "conversation-beta": "Compras semanales de Nvidia",
  "conversation-gamma": "Bitcoin en lo que va del año",
  "conversation-delta": "Aportes mensuales al índice",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const IDLE_ACTIVITY = {
  operation: { status: "idle" as const, kind: null, updated_at: CREATED_AT },
  attention: { status: "none" as const, cursor: null },
};

function conversation(id: string, title: string) {
  return {
    type: "chat" as const,
    id,
    conversation_id: id,
    title,
    title_source: "system_generated",
    subtitle: "",
    pinned: false,
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
    activity: IDLE_ACTIVITY,
  };
}

function confirmationCard(isSpanish: boolean) {
  return {
          version: "argus_confirmation/v1",
          status: "awaiting_confirmation",
          title: isSpanish ? "Listo para probar" : "Ready to test",
          strategy_label: isSpanish ? "Comprar y mantener" : "Buy and hold",
          rows: [
            {
              key: "assets",
              label: isSpanish ? "Activos" : "Assets",
              value: "AAPL",
            },
            {
              key: "period",
              label: isSpanish ? "Período" : "Period",
              value: isSpanish
                ? "Últimos 12 meses · 2025-08-01 a 2026-08-01"
                : "Last 12 months · 2025-08-01 to 2026-08-01",
            },
            {
              key: "capital",
              label: isSpanish ? "Capital" : "Capital",
              value: "$10,000",
            },
            {
              key: "benchmark",
              label: isSpanish ? "Referencia" : "Benchmark",
              value: "SPY",
            },
          ],
          actions: [
            { id: "run", type: "run_backtest", label: isSpanish ? "Ejecutar" : "Run test" },
            { id: "capital", type: "adjust_capital", label: isSpanish ? "Capital" : "Capital" },
            { id: "period", type: "adjust_period", label: isSpanish ? "Fechas" : "Dates" },
            { id: "benchmark", type: "adjust_benchmark", label: isSpanish ? "Referencia" : "Benchmark" },
            { id: "cancel", type: "cancel_confirmation", label: isSpanish ? "Cancelar" : "Cancel" },
          ],
        };
}

function resultMessages(language: "en" | "es-419") {
  const isSpanish = language === "es-419";
  return [
    {
      id: "message-user-1",
      role: "user",
      content: isSpanish
        ? "Compara Apple con SPY durante los últimos 12 meses."
        : "Compare Apple with SPY over the last 12 months.",
      created_at: CREATED_AT,
      metadata: {},
    },
    {
      id: "message-assistant-1",
      role: "assistant",
      content: isSpanish
        ? "Apple superó a SPY en el período probado."
        : "Apple outperformed SPY across the tested window.",
      created_at: CREATED_AT,
      metadata: {
        next_experiments: {
          version: "argus_next_experiments/v1",
          rows: [
            {
              kind: "change_date_range",
              label: "Test a different date range",
              label_key: "chat.next_experiments.labels.change_date_range",
              label_short: "Different dates",
              label_short_key:
                "chat.next_experiments.labels_short.change_date_range",
            },
            {
              kind: "same_setup_peer_asset",
              label: "Test the same setup on a similar asset",
              label_key: "chat.next_experiments.labels.same_setup_peer_asset",
              label_short: "Similar asset",
              label_short_key:
                "chat.next_experiments.labels_short.same_setup_peer_asset",
            },
            {
              kind: "compare_buy_and_hold",
              label: "Compare with buy and hold",
              label_key: "chat.next_experiments.labels.compare_buy_and_hold",
              label_short: "Compare with holding",
              label_short_key:
                "chat.next_experiments.labels_short.compare_buy_and_hold",
            },
          ],
        },
        discovery: {
          schema_version: "argus_asset_discovery/v1",
          kind: "asset_discovery",
          relationship: "peer",
          query_summary: "Apple peers",
          retrieved_at: CREATED_AT,
          unverified_names: [],
          can_request_search: false,
          candidates: [
            {
              symbol: "MSFT",
              name: "Microsoft",
              asset_class: "equity",
              reason_text: "Large cap technology peer",
              source_indices: [0],
            },
            {
              symbol: "NVDA",
              name: "Nvidia",
              asset_class: "equity",
              reason_text: "Same sector, different driver",
              source_indices: [1],
            },
          ],
          sources: [
            {
              url: "https://example.com/apple-earnings",
              domain: "example.com",
              title: "Apple quarterly earnings summary",
              source_date: "2026-07-20",
            },
            {
              url: "https://example.org/spy-overview",
              domain: "example.org",
              title: "SPY index overview and methodology",
              source_date: "2026-06-11",
            },
            {
              url: "https://example.net/market-window",
              domain: "example.net",
              title: "Twelve month market window review",
              source_date: "2026-05-02",
            },
          ],
        },
      },
    },
    ...Array.from({ length: 6 }, (_, index) => [
      {
        id: `message-user-${index + 2}`,
        role: "user",
        content: isSpanish
          ? `Pregunta de seguimiento ${index + 1}.`
          : `Follow-up question ${index + 1}.`,
        created_at: CREATED_AT,
        metadata: {},
      },
      {
        id: `message-assistant-${index + 2}`,
        role: "assistant",
        content: isSpanish
          ? `Respuesta de seguimiento ${index + 1}.`
          : `Follow-up answer ${index + 1}.`,
        created_at: CREATED_AT,
        metadata:
          index === 1
            ? {
                result_card: {
                  version: "argus_result/v1",
                  run_id: "run-alpha",
                  title: isSpanish
                    ? "Apple, comprar y mantener"
                    : "Apple buy and hold",
                  strategy_label: isSpanish
                    ? "Comprar y mantener"
                    : "Buy and hold",
                  symbols: ["AAPL"],
                  benchmark_symbol: "SPY",
                  status: "completed",
                  date_range: {
                    start: "2025-08-01",
                    end: "2026-08-01",
                    display: isSpanish
                      ? "1 ago 2025 a 1 ago 2026"
                      : "Aug 1 2025 to Aug 1 2026",
                  },
                  rows: [
                    {
                      key: "total_return",
                      label: isSpanish ? "Retorno total" : "Total return",
                      value: "+18.4%",
                    },
                    {
                      key: "benchmark_return",
                      label: isSpanish ? "Referencia" : "Benchmark",
                      value: "+11.2%",
                    },
                  ],
                  assumptions: [],
                  actions: [],
                  evidence_artifact_id: "evidence-alpha",
                },
              }
            : index === 5
              ? { confirmation_card: confirmationCard(isSpanish) }
              : {},
      },
    ]).flat(),
  ];
}

export async function installMobileShellFixture(
  page: Page,
  options: {
    account?: FixtureAccount;
    language?: "en" | "es-419";
    theme?: "dark" | "light";
  } = {},
): Promise<void> {
  const account = options.account ?? "registered";
  const language = options.language ?? "en";
  const theme = options.theme ?? "dark";
  const isGuest = account === "guest";

  await page.addInitScript(
    ([lang, storedTheme]) => {
      window.localStorage.setItem("i18nextLng", lang);
      window.localStorage.setItem("argus:sidebar_mode", "expanded");
      window.localStorage.setItem("argus-theme", storedTheme);
    },
    [language, theme],
  );

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: USER_ID,
          email: isGuest ? null : "shell@example.com",
          username: isGuest ? null : "shell",
          display_name: isGuest ? null : "Shell Tester",
          language,
          locale: language === "es-419" ? "es-419" : "en-US",
          onboarding: {
            completed: true,
            stage: "completed",
            language_confirmed: true,
            primary_goal: null,
          },
        },
        account_kind: isGuest ? "guest" : "registered",
        guest: isGuest
          ? { expires_at: "2026-08-14T12:00:00Z", workspace_id: "guest-workspace" }
          : null,
        capabilities: {
          can_create_additional_conversation: !isGuest,
          can_manage_conversation: !isGuest,
          can_save_decision: !isGuest,
          can_manage_account: !isGuest,
          can_use_omnisearch: true,
          can_search_current_workspace: true,
          can_use_grounded_discovery: true,
          can_submit_feedback: true,
        },
        public_account_access_enabled: false,
      });
    }

    if (path.endsWith("/api/v1/conversations")) {
      const items = isGuest
        ? [CONVERSATIONS[0]]
        : CONVERSATIONS;
      return json(route, {
        items: items.map((entry) =>
          conversation(
            entry.id,
            language === "es-419" ? SPANISH_TITLES[entry.id] : entry.title,
          ),
        ),
        next_cursor: null,
      });
    }

    if (/\/api\/v1\/conversations\/[^/]+\/activity$/.test(path)) {
      return json(route, IDLE_ACTIVITY);
    }

    if (/\/api\/v1\/conversations\/[^/]+\/messages$/.test(path)) {
      return json(route, { items: resultMessages(language), next_cursor: null });
    }

    if (path.endsWith("/api/v1/history")) {
      const items = (isGuest ? [CONVERSATIONS[0]] : CONVERSATIONS).map((entry) =>
        conversation(
          entry.id,
          language === "es-419" ? SPANISH_TITLES[entry.id] : entry.title,
        ),
      );
      return json(route, { items, next_cursor: null });
    }

    if (path.endsWith("/api/v1/search")) {
      const items = (isGuest ? [CONVERSATIONS[0]] : CONVERSATIONS).map(
        (entry) => ({
          type: "conversation" as const,
          id: entry.id,
          conversation_id: entry.id,
          title:
            language === "es-419" ? SPANISH_TITLES[entry.id] : entry.title,
          archived: false,
          matched_text: "Apple, SPY, twelve month window.",
          updated_at: CREATED_AT,
          match: {
            layer: "conversation" as const,
            fragment: "Apple, SPY, twelve month window.",
            count: 1,
          },
          dossier:
            entry.id === "conversation-alpha"
              ? {
                  run_id: "run-alpha",
                  run_label:
                    language === "es-419"
                      ? "Apple, comprar y mantener"
                      : "Apple buy and hold",
                  completed_at: CREATED_AT,
                  result_message_id: "message-assistant-1",
                  tested: {
                    symbols: ["AAPL"],
                    strategy_family: "buy_and_hold",
                    cadence: null,
                    timeframe: "1d",
                    start_date: "2025-08-01",
                    end_date: "2026-08-01",
                  },
                  outcome: {
                    run_label:
                      language === "es-419"
                        ? "Apple, comprar y mantener"
                        : "Apple buy and hold",
                    completed_at: CREATED_AT,
                    benchmark_symbol: "SPY",
                    quick_take:
                      language === "es-419"
                        ? "Apple superó a SPY en el período probado."
                        : "Apple outperformed SPY across the tested window.",
                    metrics: [
                      {
                        name:
                          language === "es-419" ? "Retorno total" : "Total return",
                        value: "+18.4%",
                      },
                      {
                        name: language === "es-419" ? "Referencia" : "Benchmark",
                        value: "+11.2%",
                      },
                      {
                        name:
                          language === "es-419" ? "Caída máxima" : "Max drawdown",
                        value: "-9.1%",
                      },
                    ],
                  },
                  decision: null,
                  actions: [
                    {
                      type: "retest_run" as const,
                      source_run_id: "run-alpha",
                      run_label:
                        language === "es-419"
                          ? "Apple, comprar y mantener"
                          : "Apple buy and hold",
                      window_policy:
                        "preserve_start_ending_latest_available" as const,
                      contract_version: "argus_retest_run/v2" as const,
                      state: "new_data_available" as const,
                      reason_code: null,
                      repair: null,
                    },
                  ],
                }
              : null,
          total_runs: 1,
          decided_runs: 0,
          decision_states: [],
        }),
      );
      return json(route, { items, next_cursor: null, ledger_groups: [] });
    }

    if (path.endsWith("/api/v1/memory/availability")) {
      return json(route, { available: false, reason: "disabled" });
    }

    if (path.endsWith("/api/v1/starter-prompts")) {
      return json(route, { prompts: [] });
    }

    return json(route, {});
  });
}
