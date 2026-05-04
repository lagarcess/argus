import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { resultCardFromRun } from "../lib/argus-api";

const root = join(import.meta.dir, "..");

describe("Argus Alpha frontend contract", () => {
  test("maps API conversation_result_card into chat result payload", () => {
    const result = resultCardFromRun({
      id: "run-1",
      status: "completed",
      asset_class: "equity",
      symbols: ["TSLA"],
      allocation_method: "equal_weight",
      benchmark_symbol: "SPY",
      metrics: { aggregate: {}, by_symbol: {} },
      config_snapshot: {},
      created_at: "2026-04-24T00:00:00Z",
      conversation_result_card: {
        title: "TSLA RSI Mean Reversion",
        date_range: {
          start: "2025-04-23",
          end: "2026-04-23",
          display: "April 23, 2025 to April 23, 2026",
        },
        status_label: "Simulation Complete",
        rows: [
          { key: "total_return_pct", label: "Total Return (%)", value: "+12.4%" },
        ],
        assumptions: ["Long-only.", "Benchmark: SPY."],
        actions: [{ type: "add_to_collection", label: "Add strategy to collection" }],
        benchmark_note: "Long-only. Benchmark: SPY."
      },
    });

    expect(result.strategyName).toBe("TSLA RSI Mean Reversion");
    expect(result.period).toBe("April 23, 2025 to April 23, 2026");
    expect(result.metrics).toEqual([{ label: "Total Return (%)", value: "+12.4%" }]);
    expect(result.benchmarkNote).toBe("Long-only. Benchmark: SPY.");
  });

  test("chat shell uses Collections terminology instead of Portfolios", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const files = [
      chat,
      readFileSync(join(root, "components/views/CollectionsView.tsx"), "utf-8"),
    ].join("\n");

    expect(files).toContain("CollectionsView");
    expect(files).toContain("common.add_to_collection");
    expect(files.toLowerCase()).not.toContain("portfolio");
  });

  test("chat header keeps the history options affordance", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain('aria-label="Chat options"');
    expect(chat).toContain("chat.view_history");
    expect(chat).toContain("common.add_to_collection");
    expect(chat).not.toContain('aria-label="Archived chats"');
  });

  test("chat result messages preserve assistant explanation next to card", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");

    expect(chat).toContain("content: m.content");
    expect(message).toContain('message.kind === "strategy_result"');
    expect(message).toContain("message.content &&");
    expect(message).toContain("<StrategyResultCard result={message.result} />");
  });

  test("chat renders structured confirmation cards with input actions", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain('event: "confirmation"');
    expect(chat).toContain('kind: "strategy_confirmation"');
    expect(chat).toContain("setInputActions(confirmation.actions ?? [])");
    expect(chat).toContain("slide-in-from-bottom-2");
    expect(message).toContain("<StrategyConfirmationCard confirmation={message.confirmation} />");
  });

  test("chat includes onboarding goal cards and hidden onboarding protocol", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("data-testid=\"onboarding-goal-cards\"");
    expect(chat).toContain("data-testid=\"onboarding-skip\"");
    expect(chat).toContain("__ONBOARDING_GOAL__:");
    expect(chat).toContain("__ONBOARDING_SKIP__");
  });

  test("chat sidebar uses global search api and cursor pagination hooks", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(chat).toContain("searchGlobal({ q: query, limit: 20 })");
    expect(chat).toContain("loadMoreSearch");
    expect(api).toContain("cursor?: string");
    expect(api).toContain("export async function searchGlobal");
  });

  test("login surface text is localized through auth.login keys", () => {
    const login = readFileSync(join(root, "app/login/page.tsx"), "utf-8");
    expect(login).toContain("auth.login.subtitle");
    expect(login).toContain("auth.login.email_placeholder");
    expect(login).toContain("auth.login.password_placeholder");
    expect(login).toContain("t(\"auth.login.submit\"");
  });

  test("landing onboarding continues into chat after completion", () => {
    const page = readFileSync(join(root, "app/page.tsx"), "utf-8");

    expect(page).toContain('postCompleteHref="/chat"');
  });

  test("settings subscription section is feature-flagged off by default", () => {
    const settings = readFileSync(join(root, "components/views/SettingsView.tsx"), "utf-8");

    expect(settings).toContain("NEXT_PUBLIC_ARGUS_SHOW_SUBSCRIPTION");
    expect(settings).toContain("{showSubscriptionSection && (");
  });

  test("strategies surface renders dynamic metrics based on preferences", () => {
    const file = readFileSync(join(root, "components/views/StrategiesView.tsx"), "utf-8");
    expect(file).toContain("strategy.columns.map(");
    expect(file).toContain("asset.pills.map(");
    expect(file).not.toContain('className="grid grid-cols-4 gap-2 items-end pb-2 sticky top-[-1px]');
    expect(file).toContain("style={{ gridTemplateColumns: `repeat(${strategy.columns.length + 1}, minmax(0, 1fr))` }}");
  });


  test("no shadow utility classes are used in chat input", () => {
    const file = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");
    expect(file).not.toContain("shadow");
  });

});
