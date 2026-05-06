import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { parseChatStreamFrame, resultCardFromRun } from "../lib/argus-api";

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
        actions: [{ type: "save_strategy", label: "Save strategy" }],
        benchmark_note: "Long-only. Benchmark: SPY.",
        chart: {
          kind: "portfolio_equity",
          series: [{ time: "2026-01-02", value: 10000 }],
          attribution: "TradingView Lightweight Charts",
        },
      },
    });

    expect(result.strategyName).toBe("TSLA RSI Mean Reversion");
    expect(result.period).toBe("April 23, 2025 to April 23, 2026");
    expect(result.metrics).toEqual([{ label: "Total Return (%)", value: "+12.4%" }]);
    expect(result.benchmarkNote).toBe("Long-only. Benchmark: SPY.");
    expect(result.chart?.kind).toBe("portfolio_equity");
  });

  test("collections remain launch-gated instead of removed", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const files = [
      chat,
      readFileSync(join(root, "components/views/CollectionsView.tsx"), "utf-8"),
    ].join("\n");

    expect(files).toContain("CollectionsView");
    expect(chat).toContain("NEXT_PUBLIC_COLLECTIONS_ENABLED");
    expect(chat).toContain("collectionsEnabled");
    expect(files.toLowerCase()).not.toContain("portfolio");
  });

  test("chat header keeps the history options affordance", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain('aria-label="Chat options"');
    expect(chat).toContain("chat.view_history");
    expect(chat).toContain("{collectionsEnabled && (");
    expect(chat).not.toContain('aria-label="Archived chats"');
  });

  test("chat result messages preserve assistant explanation next to card", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");

    expect(chat).toContain("content: m.content");
    expect(message).toContain('message.kind === "strategy_result"');
    expect(message).toContain("message.content &&");
    expect(message).toContain("<StrategyResultCard result={message.result} onAction={onAction} />");
    expect(message.indexOf("<StrategyResultCard result={message.result} onAction={onAction} />")).toBeLessThan(
      message.indexOf("message.content &&"),
    );
  });

  test("result card renders save inside the card and charts portfolio equity", () => {
    const card = readFileSync(join(root, "components/chat/StrategyResultCard.tsx"), "utf-8");
    const chart = readFileSync(join(root, "components/chat/ResultEquityChart.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(card).toContain("<ResultEquityChart chart={result.chart} />");
    expect(card).toContain('action.type === "save_strategy"');
    expect(card).toContain("<Save");
    expect(chat).toContain('action.type !== "save_strategy"');
    expect(chart).toContain("BaselineSeries");
    expect(chart).toContain("createSeriesMarkers");
    expect(chart).toContain("buildVisibleSeriesMarkers");
    expect(chart).toContain("selectVisibleTradeMarkers");
    expect(chart).toContain("subscribeVisibleLogicalRangeChange");
    expect(chart).toContain("markersApi.setMarkers");
    expect(chart).toContain("TODO(launch): Provide correct TradingView attribution before launch.");
    expect(chart).toContain("attributionLogo: false");
    expect(chart).toContain('const CHART_POSITIVE_COLOR = "#70a38d"');
    expect(chart).toContain('const CHART_NEGATIVE_COLOR = "#b85c5c"');
    expect(chart).toContain('const BUY_POSITIVE_MARKER_COLOR = "#70a38d"');
    expect(chart).toContain('const SELL_NEGATIVE_MARKER_COLOR = "#b85c5c"');
    expect(chart).not.toContain("#315d97");
    expect(chart).not.toContain("#a98b2d");
    expect(chart).toContain('data-testid="result-equity-chart"');
    expect(chart).toContain("normalizeChartTime");
  });

  test("chat renders structured confirmation cards with input actions", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain('event: "final"');
    expect(chat).toContain('kind: "strategy_confirmation"');
    expect(chat).toContain("setInputActions(confirmation.actions ?? [])");
    expect(chat).toContain("slide-in-from-bottom-2");
    expect(message).toContain("<StrategyConfirmationCard confirmation={message.confirmation} />");
  });

  test("chat stream parser consumes canonical data-only SSE frames", () => {
    const stage = parseChatStreamFrame('data: {"type":"stage_start","stage":"execute"}');
    const token = parseChatStreamFrame('data: {"type":"token","content":"Running"}');
    const done = parseChatStreamFrame("data: [DONE]");

    expect(stage).toEqual({ event: "stage_start", data: { stage: "execute" } });
    expect(token).toEqual({ event: "token", data: { text: "Running" } });
    expect(done).toEqual({ event: "done", data: { message_id: null } });
  });

  test("chat status is driven by backend stage_start events", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const locale = readFileSync(join(root, "public/locales/en/common.json"), "utf-8");

    expect(chat).toContain('event.event === "stage_start"');
    expect(chat).toContain("chat.status.${event.data.stage}");
    expect(locale).toContain('"interpret": "Understanding your idea..."');
    expect(locale).toContain('"execute": "Running backtest..."');
  });

  test("chat restores jump-to-latest affordance without forced reading jumps", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("scrollContainerRef");
    expect(chat).toContain("showJumpToLatest");
    expect(chat).toContain('aria-label="Jump to latest"');
    expect(chat).toContain("distanceFromBottom > JUMP_TO_LATEST_THRESHOLD_PX");
    expect(chat).toContain("scrollToLatest");
    expect(chat).toContain("shouldAutoScrollRef.current");
  });

  test("chat hydrates persisted structured cards from message metadata", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain("metadata?: Record<string, unknown> | null");
    expect(chat).toContain("metadata.confirmation_card");
    expect(chat).toContain("metadata.result_card");
    expect(chat).toContain("isBreakdownActionMetadata(metadata)");
    expect(chat).toContain('chatAction.type === "show_breakdown"');
    expect(chat).toContain("resultCardFromConversationCard");
  });

  test("chat consumes result action chips after breakdown is requested", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("consumeInputAction");
    expect(chat).toContain('action.type === "show_breakdown"');
    expect(chat).toContain('type !== "show_breakdown"');
    expect(chat).toContain("setInputActions(consumeInputAction(action, inputActions))");
  });

  test("chat resumes active conversation instead of creating a fresh one on reload", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("ACTIVE_CONVERSATION_STORAGE_KEY");
    expect(chat).toContain("readActiveConversationId");
    expect(chat).toContain("persistActiveConversationId");
    expect(chat).toContain("getConversationMessages(activeConversationId");
  });

  test("history menu reuses structured conversation hydration", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("hydrateMessagesFromApi");
    expect(chat).toContain("void loadConversation(item.id)");
    expect(chat).not.toContain('kind: m.content.includes("result") ? "strategy_result" : "text"');
  });

  test("spanish remains registered behind a feature flag", () => {
    const languages = readFileSync(join(root, "lib/language-features.ts"), "utf-8");
    const i18n = readFileSync(join(root, "lib/i18n.ts"), "utf-8");

    expect(languages).toContain('code: "es-419"');
    expect(languages).toContain("NEXT_PUBLIC_ENABLE_SPANISH");
    expect(i18n).toContain("ENABLED_LANGUAGE_CODES");
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

  test("chat hides backend enum labels and technical runtime errors", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const locale = readFileSync(join(root, "public/locales/en/common.json"), "utf-8");

    expect(input).toContain("displayDiscoveryDescription");
    expect(input).toContain("Currency Pair");
    expect(chat).not.toContain("event.data.detail || t('chat.error_backtest')");
    expect(locale).not.toContain("Check that the API is running");
    expect(locale).not.toContain("add the asset, amount, and time period");
  });

  test("chat stream errors preserve status for stale conversation recovery", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain("class ChatStreamError");
    expect(api).toContain("response.status");
    expect(chat).toContain("err instanceof ChatStreamError");
    expect(chat).toContain("err.status === 404");
    expect(chat).toContain("clearActiveConversationId()");
    expect(chat).toContain("await streamToConversation(conversation.id)");
  });
});
