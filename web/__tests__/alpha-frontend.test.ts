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
          { key: "cash_value", label: "Cash Value ($)", value: "$1.0k -> $2.0k" },
          { key: "benchmark_delta", label: "Vs benchmark", value: "+4.2 pts vs SPY" },
          { key: "max_drawdown_pct", label: "Max Drawdown", value: "-8.1%" },
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
    expect(result.metrics).toEqual([
      { label: "Ending value", value: "$1.0k -> $2.0k" },
      { label: "Total return", value: "+12.4%" },
      { label: "Compared with SPY", value: "+4.2 pts vs SPY" },
      { label: "Worst drop", value: "-8.1%" },
    ]);
    expect(result.benchmarkNote).toBeUndefined();
    expect(result.chart?.kind).toBe("portfolio_equity");
  });

  test("collections are indefinitely deferred from private-alpha UI", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");
    const settings = readFileSync(join(root, "components/views/SettingsView.tsx"), "utf-8");
    const palette = readFileSync(join(root, "components/sidebar/ChatCommandPalette.tsx"), "utf-8");
    const flags = readFileSync(join(root, "lib/private-alpha-flags.ts"), "utf-8");

    expect(flags).toContain("NEXT_PUBLIC_COLLECTIONS_ENABLED");
    expect(chat).toContain("collectionsEnabled");
    expect(chat).not.toContain("trigger_create_collection");
    expect(chat).not.toContain("CollectionsView");
    expect(chat).not.toContain("CollectionPicker");
    expect(sidebar).not.toContain("Collections");
    expect(settings).not.toContain("collection");
    expect(settings).toContain("items.filter(isDeletedItemVisible)");
    expect(settings).toContain("strategiesEnabled");
    expect(settings).not.toContain("<Layers");
    expect(settings).not.toContain("{item.type}");
    expect(palette).toContain('item.type !== "chat"');
  });

  test("chat header keeps the history options affordance", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain('aria-label="Chat options"');
    expect(chat).toContain("chat.view_history");
    expect(chat).not.toContain("chat.add_to_collection");
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

  test("result cards render a separate trust strip and compact assumption details", () => {
    const card = readFileSync(join(root, "components/chat/StrategyResultCard.tsx"), "utf-8");
    const en = readFileSync(join(root, "public/locales/en/common.json"), "utf-8");

    expect(card).toContain("TrustRail");
    expect(card).toContain("ExecutionDetails");
    expect(card).toContain("view.details");
    expect(card).toContain("result_trust_strip");
    expect(card).toContain("Result trust context");
    expect(card).not.toContain("result.assumptions.map");
    expect(en).toContain("Historical simulation · No fees/slippage · Not advice");
  });

  test("result readouts use a structured editorial treatment", () => {
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const css = readFileSync(join(root, "app/globals.css"), "utf-8");

    expect(message).toContain("function ResultReadout");
    expect(message).toContain('aria-label="Result readout"');
    expect(css).toContain(".argus-result-readout::before");
    expect(css).toContain("text-wrap: pretty");
    expect(css).not.toContain("argus-result-readout shadow");
  });

  test("result breakdowns render as a distinct fact-grounded surface", () => {
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const css = readFileSync(join(root, "app/globals.css"), "utf-8");

    expect(message).toContain("function ResultBreakdown");
    expect(message).toContain('aria-label="Result breakdown"');
    expect(message).toContain("argus-result-section-label");
    expect(message).toContain("Breakdown");
    expect(message).toContain('message.contentPresentation === "result_breakdown" && message.content?.trim()');
    expect(chat).toContain('action?.type === "show_breakdown"');
    expect(chat).toContain('contentPresentation:');
    expect(css).toContain(".argus-result-breakdown::before");
    expect(css).toContain('content: ""');
    expect(css).toContain("border-left");
    expect(css).not.toContain("argus-result-breakdown shadow");
  });

  test("result card hides save by default while keeping explain and refine actions", () => {
    const card = readFileSync(join(root, "components/chat/StrategyResultCard.tsx"), "utf-8");
    const flags = readFileSync(join(root, "lib/private-alpha-flags.ts"), "utf-8");
    const labelHelper = readFileSync(join(root, "lib/result-card-display.ts"), "utf-8");
    const chart = readFileSync(join(root, "components/chat/ResultEquityChart.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(card).toContain("<ResultEquityChart");
    expect(card).toContain('presentation="heroDeltaEvidence"');
    expect(card).toContain("appearanceOverride={appearance}");
    expect(flags).toContain("NEXT_PUBLIC_STRATEGIES_ENABLED");
    expect(card).toContain('action.type !== "save_strategy"');
    expect(labelHelper).toContain('"Explain result"');
    expect(labelHelper).toContain('"Refine idea"');
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

  test("chat renders structured confirmation cards with card-scoped actions only", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain('event: "final"');
    expect(chat).toContain('kind: "strategy_confirmation"');
    expect(chat).toContain('latestAi?.kind === "strategy_confirmation"');
    expect(chat).toContain("isCardScopedAction");
    expect(chat).toContain("hasActiveArtifactActionSet(messages)");
    expect(chat).toContain("visibleComposerActions(inputActions)");
    expect(chat).not.toContain("setInputActions(confirmation.actions ?? [])");
    expect(chat).not.toContain("visibleInputActions(inputActions).map");
    expect(chat).not.toContain('event.event === "confirmation"');
    expect(chat).not.toContain('event.event === "result"');
    expect(chat).toContain("slide-in-from-bottom-2");
    expect(message).toContain("<StrategyConfirmationCard confirmation={message.confirmation} onAction={onAction} />");
  });

  test("artifact cards use compositor-safe reveal motion with a reduced-motion opt out", () => {
    const css = readFileSync(join(root, "app/globals.css"), "utf-8");
    const resultCard = readFileSync(join(root, "components/chat/StrategyResultCard.tsx"), "utf-8");
    const confirmationCard = readFileSync(join(root, "components/chat/StrategyConfirmationCard.tsx"), "utf-8");

    expect(resultCard).toContain("argus-card-reveal");
    expect(resultCard).toContain("argus-result-reveal-positive");
    expect(resultCard).toContain("argus-result-reveal-caution");
    expect(confirmationCard).toContain("argus-card-reveal");
    expect(confirmationCard).toContain("argus-confirmation-reveal");
    expect(css).toContain(".argus-card-reveal");
    expect(css).toContain("will-change: transform, opacity, border-color;");
    expect(css).toContain("translate3d(0, 10px, 0)");
    expect(css).toContain("translate3d(0, 12px, 0)");
    expect(css).toContain("transform: translate3d(0, 0, 0) scale(1);");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain("animation: none;");
  });

  test("composer hides artifact actions whenever any active card owns them", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    const activeArtifactHelper = chat.slice(
      chat.indexOf("function hasActiveArtifactActionSet"),
      chat.indexOf("function consumeInputAction"),
    );

    expect(activeArtifactHelper).toContain("messages.some");
    expect(activeArtifactHelper).toContain("confirmation.confirmation_state !== \"active\"");
    expect(activeArtifactHelper).toContain("actionHasCardScopedOwnership");
    expect(activeArtifactHelper).not.toContain("latestAi");
    expect(chat).toContain("const composerActions = hasActiveArtifactActionSet(messages)");
    expect(chat).toContain("visibleComposerActions(inputActions)");
  });

  test("chat supersedes older confirmation cards when a newer draft appears", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const artifactHistory = readFileSync(
      join(root, "components/chat/artifact-history.ts"),
      "utf-8",
    );
    const card = readFileSync(join(root, "components/chat/StrategyConfirmationCard.tsx"), "utf-8");
    const types = readFileSync(join(root, "components/chat/types.ts"), "utf-8");

    expect(types).toContain('confirmation_state?: "active" | "superseded" | "cancelled"');
    expect(types).toContain("confirmation_id?: string");
    expect(chat).toContain("normalizeConfirmationHistory");
    expect(chat).toContain("from \"./artifact-history\"");
    expect(artifactHistory).toContain("supersedePriorConfirmations");
    expect(artifactHistory).toContain("function isTerminalConfirmation");
    expect(card).toContain('confirmation.confirmation_state === "superseded"');
    expect(card).toContain('confirmation.confirmation_state === "cancelled"');
    expect(card).toContain('isCancelled ? "Draft canceled" : "Updated"');
  });

  test("chat supersedes active confirmations when a later turn asks for recovery", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("supersedeOpenConfirmations");
    expect(chat).toContain("finalStageOutcome");
    expect(chat).toContain('finalStageOutcome === "await_user_reply"');
    expect(chat).toContain('finalStageOutcome === "needs_clarification"');
  });

  test("chat final payload accepts pending strategy metadata", () => {
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain("pending_strategy?");
    expect(api).toContain("missing_required_fields?: string[]");
    expect(api).toContain("strategy: Record<string, unknown>");
    expect(api).toContain("pending_resolution?");
  });

  test("confirmation action chips render as action transcript items", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const types = readFileSync(join(root, "components/chat/types.ts"), "utf-8");

    expect(types).toContain('"action"');
    expect(chat).toContain('kind: action?.type ? "action" : "text"');
    expect(chat).toContain("selectedAction: action");
    expect(chat).toContain("metadata.chat_action");
    expect(message).toContain('message.kind === "action"');
  });

  test("streaming backend errors keep backend detail when provided", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("chatStreamErrorText(");
    expect(chat).toContain("event.data.detail");
    expect(chat).toContain("err instanceof ChatStreamError && err.message");
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

  test("latest pending assistant response hides feedback before stage_start arrives", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");

    expect(chat).toContain("isStreamingResponse");
    expect(chat).toContain("latestAiIndex");
    expect(chat).toContain("isWorkingMessage");
    expect(chat).toContain('(msg.content ?? "") === ""');
    expect(chat).toContain("isStreaming={isWorkingMessage}");
    expect(message).toContain("{!isUser && !isStreaming && !copyFeedback && (");
    expect(message).toContain("{copyFeedback && (");
  });

  test("stream status hides once assistant tokens are visible", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("latestAssistantContent");
    expect(chat).toContain("const showStreamStatus = Boolean(streamStatus && latestAssistantContent.length === 0)");
    expect(chat).toContain("{showStreamStatus && (");
  });

  test("chat composer prevents overlapping turns while stream is active", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");

    expect(chat).toContain("if (isStreamingResponse) return;");
    expect(chat).toContain("<ChatInput onSend={handleSend} disabled={isStreamingResponse} />");
    expect(chat).toContain('if (event.event === "final")');
    expect(chat).toContain("setIsStreamingResponse(false);");
    expect(input).toContain("disabled?: boolean");
    expect(input).toContain("if (disabled) return;");
    expect(input).toContain("contentEditable={!disabled}");
    expect(input).toContain("disabled={composerIsEmpty || disabled}");
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
    const artifactHistory = readFileSync(
      join(root, "components/chat/artifact-history.ts"),
      "utf-8",
    );

    expect(api).toContain("metadata?: Record<string, unknown> | null");
    expect(chat).toContain("metadata.confirmation_card");
    expect(chat).toContain("metadata.result_card");
    expect(chat).toContain("isBreakdownActionMetadata(metadata)");
    expect(artifactHistory).toContain('chatAction.type === "show_breakdown"');
    expect(chat).toContain("resultCardFromConversationCard");
  });

  test("result actions carry canonical run and conversation context", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("hydrateResultActions");
    expect(chat).toContain("runId: run.id");
    expect(chat).toContain("strategyId: run.strategy_id ?? null");
    expect(chat).toContain("conversationId: run.conversation_id ?? undefined");
    expect(chat).toContain("metadata.result_conversation_id");
    expect(chat).toContain("resultActionContextFromMetadata(metadata, card)");
    expect(chat).toContain("assetClassOrUndefined(factBank?.asset_class)");
    expect(chat).not.toContain('template: "",\n        assetClass: "equity"');
    expect(chat).toContain("resultActionRequiresRunContext");
    expect(chat).toContain("hasResultActionContext(context.runId, context.conversationId)");
    expect(chat).toContain("presentation: \"result\"");
  });

  test("artifact actions stay attached to historical cards", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("markComposerActionsInactive");
    expect(chat).not.toContain("prev.map((m) => ({ ...m, actions: undefined }))");
    expect(chat).toContain("message.result.actions");
    expect(chat).toContain("message.confirmation.actions");
  });

  test("confirmation cards render active artifact actions", () => {
    const card = readFileSync(join(root, "components/chat/StrategyConfirmationCard.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");

    expect(card).toContain("onAction?: (action: ChatActionOption) => void");
    expect(card).toContain("confirmation.actions");
    expect(card).toContain('confirmation.confirmation_state === "active"');
    expect(card).toContain("!confirmation.confirmation_state");
    expect(card).not.toContain("ArrowRight");
    expect(message).toContain("<StrategyConfirmationCard confirmation={message.confirmation} onAction={onAction} />");
  });

  test("result cards render artifact scoped actions and saved state", () => {
    const card = readFileSync(join(root, "components/chat/StrategyResultCard.tsx"), "utf-8");
    const locale = readFileSync(join(root, "public/locales/en/common.json"), "utf-8");

    expect(card).toContain('action.type === "show_breakdown"');
    expect(card).toContain('action.type === "refine_strategy"');
    expect(card).toContain('action.type === "save_strategy"');
    expect(card).toContain("result.savedStrategyId");
    expect(card).toContain("chat.saved");
    expect(locale).toContain('"saved": "Saved"');
  });

  test("chat updates saved state from save strategy final payloads", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const types = readFileSync(join(root, "components/chat/types.ts"), "utf-8");

    expect(types).toContain("savedStrategyId?: string | null");
    expect(chat).toContain("handleSaveStrategyAction");
    expect(chat).toContain("hiddenSaveActionMessageIdsFromApi");
    expect(chat).toContain("markResultCardSaved");
    expect(chat).toContain("saved_strategy_id");
    expect(chat).toContain("result_strategy_id");
    expect(chat).toContain('action.type === "save_strategy"');
  });

  test("saved result state is not inferred from plain result strategy linkage", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    const metadataHelper = chat.slice(
      chat.indexOf("function savedStrategyIdFromMetadata"),
      chat.indexOf("function savedStrategyIdFromFinalPayload"),
    );
    const finalPayloadHelper = chat.slice(
      chat.indexOf("function savedStrategyIdFromFinalPayload"),
      chat.indexOf("function resultRunIdFromFinalPayload"),
    );

    expect(metadataHelper).toContain("saved_strategy_id");
    expect(metadataHelper).not.toContain("result_strategy_id");
    expect(finalPayloadHelper).toContain("saved_strategy_id");
    expect(finalPayloadHelper).not.toContain("result_strategy_id");
  });

  test("assistant copy is artifact aware and visibly confirmed", () => {
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const en = readFileSync(join(root, "public/locales/en/common.json"), "utf-8");
    const es = readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8");

    expect(message).toContain("await navigator.clipboard.writeText");
    expect(message).toContain("copyFeedback");
    expect(message).toContain("chat.copy_success");
    expect(message).toContain("chat.copy_failed");
    expect(message).toContain('message.kind === "strategy_confirmation"');
    expect(en).toContain('"copy_success": "Copied"');
    expect(es).toContain('"copy_failed": "No se pudo copiar"');
  });

  test("chat consumes result action chips after breakdown is requested", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("consumeInputAction");
    expect(chat).toContain("consumeResultActionOnMessages");
    expect(chat).toContain("consumedResultActionsFromApi");
    expect(chat).toContain("applyConsumedResultActions");
    expect(chat).toContain('action.type === "show_breakdown"');
    expect(chat).toContain('type !== "show_breakdown"');
    expect(chat).toContain("setInputActions(consumeInputAction(action, inputActions))");
    expect(chat).toContain('latestAi?.kind === "strategy_result"');
    expect(chat).toContain("setInputActions([])");
  });

  test("chat resumes active conversation instead of creating a fresh one on reload", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("ACTIVE_CONVERSATION_STORAGE_KEY");
    expect(chat).toContain("readActiveConversationId");
    expect(chat).toContain("persistActiveConversationId");
    expect(chat).toContain("getConversationMessages(activeConversationId");
    expect(chat).toContain("const routeConversationId = readActiveConversationIdFromUrl();");
    expect(chat).toContain("const targetConversationId = routeConversationId ?? conversationId;");
    expect(chat).toContain("await streamToConversation(targetConversationId);");
  });

  test("history menu reuses structured conversation hydration", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(chat).toContain("hydrateMessagesFromApi");
    expect(chat).toContain("void loadConversation(item.id)");
    expect(chat).toContain("loadConversationForRun");
    expect(chat).toContain("getBacktestRun(item.id)");
    expect(api).toContain("export async function getBacktestRun");
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

  test("chat sidebar opens a safe command palette instead of hydrating chat previews", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const palette = readFileSync(join(root, "components/sidebar/ChatCommandPalette.tsx"), "utf-8");

    expect(chat).toContain("ChatSidebar");
    expect(chat).toContain("ChatCommandPalette");
    expect(chat).toContain("searchOverlayOpen");
    expect(chat).not.toContain("ChatOmniSearch");
    expect(palette).toContain("searchGlobal");
    expect(palette).toContain("listHistory");
    expect(palette).toContain("onOpenConversation");
    expect(palette).not.toContain("getConversationMessages");
    expect(palette).not.toContain("hydrateMessagesFromApi");
    expect(palette).not.toContain("ChatMessage");
    expect(palette).not.toContain("streamChatMessage");
    expect(palette).not.toContain("handleAction");
  });

  test("chat command palette uses global search api and cursor pagination hooks", () => {
    const palette = readFileSync(join(root, "components/sidebar/ChatCommandPalette.tsx"), "utf-8");
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(palette).toContain("searchGlobal({ q: trimmed, limit: 30 })");
    expect(palette).toContain("loadMoreSearch");
    expect(api).toContain("cursor?: string");
    expect(api).toContain("export async function searchGlobal");
  });

  test("chat command palette keeps safe hover management actions without chat hydration", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const palette = readFileSync(join(root, "components/sidebar/ChatCommandPalette.tsx"), "utf-8");

    expect(chat).toContain("onMutated={refreshHistory}");
    expect(palette).toContain("Edit2");
    expect(palette).toContain("Archive");
    expect(palette).toContain("Trash2");
    expect(palette).toContain("editingId");
    expect(palette).toContain("editingTitle");
    expect(palette).toContain("handleRenameSave");
    expect(palette).toContain("handleArchive");
    expect(palette).toContain("handleDelete");
    expect(palette).toContain("patchConversation");
    expect(palette).toContain("apiDeleteConversation");
    expect(palette).toContain('import { Tooltip } from "@/components/ui/Tooltip"');
    expect(palette).toContain('<Tooltip content={t("common.rename", "Rename")} side="top" delay={120}>');
    expect(palette).toContain('<Tooltip content={t("common.archive", "Archive")} side="top" delay={120}>');
    expect(palette).toContain('<Tooltip content={t("common.delete", "Delete")} side="top" delay={120}>');
    expect(palette).not.toContain("getConversationMessages");
    expect(palette).not.toContain("hydrateMessagesFromApi");
    expect(palette).not.toContain("ChatMessage");
    expect(palette).not.toContain("streamChatMessage");
    expect(palette).not.toContain("handleAction");
  });

  test("chat schedules bounded history refreshes for async artifact naming", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("function schedulePostTurnHistoryRefresh");
    expect(chat).toContain("listConversations");
    expect(chat).toContain("title_source");
    expect(chat).toContain("window.setTimeout");
    expect(chat).toContain("1500");
    expect(chat).toContain("5000");
    expect(chat).toContain("9000");
    expect(chat).toContain("13000");
    expect(chat).toContain("schedulePostTurnHistoryRefresh(targetConversationId);");
    expect(chat).toContain("Title/sidebar refresh is fail-open");
    expect(chat).toContain("void refreshAndCheckTitle().catch(() => undefined);");
  });

  test("feedback dialog provides rich feedback surfaces", () => {
    const dialog = readFileSync(join(root, "components/feedback/FeedbackDialog.tsx"), "utf-8");

    expect(dialog).toContain("FeedbackType");
    expect(dialog).toContain("bugTitle");
    expect(dialog).toContain("steps");
    expect(dialog).toContain("expected");
    expect(dialog).toContain("actual");
    expect(dialog).toContain("consent");
    expect(dialog).toContain("files");
    expect(dialog).toContain("Paperclip");
    expect(dialog).toContain("ChevronDown");
    expect(dialog).toContain("hasAttachments");
    expect(dialog).toContain("Maximum 5 files");
    expect(dialog).toContain("attachments_with_count");
    expect(dialog).toContain("Attachments ({{count}}/5)");
    expect(dialog).toContain("Optional: add a screenshot, sketch, or example.");
    expect(dialog).toContain("General Feedback");
    expect(dialog).toContain("Report a Bug");
    expect(dialog).toContain("Request a Feature");
    expect(dialog).toContain("I consent to the Argus team");
    expect(dialog).toContain("consent_feature");
    expect(dialog).toContain("hasConversationContext");
    expect(dialog).toContain('event.key === "Escape"');
    expect(dialog).toContain("document.addEventListener(\"keydown\"");
    expect(dialog).toContain('type === "bug"');
    expect(dialog).toContain('const title = "Provide feedback";');
    expect(dialog).toContain('"File a bug report."');
    expect(dialog).toContain('"Share feedback about your Argus experience."');
    expect(dialog).toContain('"What worked well in this response?"');
    expect(dialog).toContain('"What should be improved in this response?"');
    expect(dialog).toContain("Your current conversation context may be included to help us understand this feedback.");
    expect(dialog).toContain("App context like this page and timestamp may be included to help us understand this feedback.");
    expect(dialog).toContain("Learn more");
    expect(dialog).not.toContain("Provide positive feedback");
    expect(dialog).not.toContain("Provide negative feedback");
    expect(dialog).not.toContain("File a bug report, request a feature, or send general feedback.");
    expect(dialog).not.toContain("Tell us what made this response land or miss.");
    expect(dialog).not.toContain("ThumbsUp");
    expect(dialog).not.toContain("ThumbsDown");
  });

  test("chat message feedback controls fill only the selected thumb glyph", () => {
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(message).toContain("text-[#191c1f] dark:text-white");
    expect(message).toContain("selectedFeedbackClass");
    expect(message).toContain("selectedFeedbackIconClass");
    expect(message).toContain('rating === "positive" ? selectedFeedbackIconClass : ""');
    expect(message).toContain('rating === "negative" ? selectedFeedbackIconClass : ""');
    expect(message).not.toContain('rating === null || rating === "positive"');
    expect(message).not.toContain('rating === null || rating === "negative"');
    expect(message).not.toContain("bg-[#5a677d]/12 text-[#5a677d] dark:bg-[#c9c9cd]/12 dark:text-[#c9c9cd]");
    expect(message).not.toContain("scale-110");
    expect(message).not.toContain("bg-black text-white dark:bg-white dark:text-black");
    expect(message).not.toContain("bg-[#5ba897]/15 text-[#5ba897]");
    expect(message).not.toContain("bg-[#d66d75]/15 text-[#d66d75]");
    expect(message).toContain("MessageSquareWarning");
    expect(message).toContain("chat.report_issue");
    expect(message).toContain('onFeedback?.("rating"');
    expect(message).toContain("postFeedback");
    expect(message).toContain("conversationId?: string | null");
    expect(message).toContain("conversation_id: conversationId");
    expect(chat).toContain("conversationId={conversationId}");
  });

  test("profile menu is isolated from sidebar hover expansion", () => {
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");
    const profileMenu = readFileSync(join(root, "components/sidebar/ProfileMenu.tsx"), "utf-8");

    expect(profileMenu).toContain('import { createPortal } from "react-dom"');
    expect(profileMenu).toContain("data-profile-menu-surface");
    expect(profileMenu).toContain("handleSubmenuToggle");
    expect(profileMenu).toContain("createPortal(menu, document.body)");
    expect(sidebar).toContain("isPointerInsideSidebarRef");
    expect(sidebar).toContain("if (isProfileMenuOpen) return");
  });

  test("interactive controls expose pointer cursor affordance globally", () => {
    const globals = readFileSync(join(root, "app/globals.css"), "utf-8");

    expect(globals).toContain("button:not(:disabled)");
    expect(globals).toContain('[role="button"]:not([aria-disabled="true"])');
    expect(globals).toContain("a[href]");
    expect(globals).toContain("label[for]");
    expect(globals).toContain("cursor: pointer;");
    expect(globals).toContain("button:disabled");
    expect(globals).toContain('[aria-disabled="true"]');
    expect(globals).toContain("cursor: not-allowed;");
  });

  test("legacy auth routes redirect into the front door auth states", () => {
    const login = readFileSync(join(root, "app/login/page.tsx"), "utf-8");
    const signup = readFileSync(join(root, "app/signup/page.tsx"), "utf-8");

    expect(login).toContain('redirect("/?auth=login")');
    expect(signup).toContain('redirect("/?auth=signup")');
  });

  test("landing onboarding continues into chat after completion", () => {
    const page = readFileSync(join(root, "app/page.tsx"), "utf-8");

    expect(page).toContain('postCompleteHref="/chat"');
    expect(page).toContain("font-display text-6xl");
    expect(page).toContain("font-display flex w-full max-w-sm");
  });

  test("landing front door adapts signup and login inline", () => {
    const page = readFileSync(join(root, "app/page.tsx"), "utf-8");

    expect(page).toContain("Eye");
    expect(page).toContain("EyeClosed");
    expect(page).not.toContain("EyeOff");
    expect(page).toContain("showPassword");
    expect(page).toContain('type={showPassword ? "text" : "password"}');
    expect(page).toContain("auth.password.show");
    expect(page).toContain("auth.password.hide");
    expect(page).toContain("signupWithEmail");
    expect(page).toContain("loginWithEmail");
    expect(page).toContain('type AuthMode = "intro" | "signup" | "login"');
    expect(page).toContain('updateAuthMode("signup")');
    expect(page).toContain('const showLogin = () => updateAuthMode("login")');
    expect(page).not.toContain('const authHref = "/chat"');
    expect(page).not.toContain("href={authHref}");
    expect(page).not.toContain('href="/login"');
  });

  test("auth exits return to the clean front door", () => {
    const chatPage = readFileSync(join(root, "app/chat/page.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chatPage).toContain('redirect("/?auth=login")');
    expect(chatPage).not.toContain('redirect("/login")');
    expect(chat).toContain('window.location.href = "/"');
    expect(chat).not.toContain('window.location.href = "/?auth=login"');
    expect(chat).not.toContain('window.location.href = "/login"');
  });

  test("onboarding api error keeps the argus wordmark centered", () => {
    const gate = readFileSync(join(root, "components/onboarding/OnboardingGate.tsx"), "utf-8");

    expect(gate).toContain("font-display mb-2 text-center");
    expect(gate).toContain("onboarding.error.title");
  });

  test("front door auth states remain visible even when mock auth has a user", () => {
    const gate = readFileSync(join(root, "components/onboarding/OnboardingGate.tsx"), "utf-8");

    expect(gate).toContain('const isAuthEntry = authMode === "signup" || authMode === "login"');
    expect(gate).toContain("!isPreview && !isAuthEntry");
    expect(gate).toContain("step === \"done\" || isPreview || isAuthEntry");
  });

  test("settings subscription section is feature-flagged off by default", () => {
    const settings = readFileSync(join(root, "components/views/SettingsView.tsx"), "utf-8");

    expect(settings).toContain("NEXT_PUBLIC_ARGUS_SHOW_SUBSCRIPTION");
    expect(settings).toContain("{showSubscriptionSection && (");
  });

  test("sidebar private-alpha flags hide strategies and omnisearch without hiding recents", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");
    const flags = readFileSync(join(root, "lib/private-alpha-flags.ts"), "utf-8");

    expect(flags).toContain("NEXT_PUBLIC_STRATEGIES_ENABLED");
    expect(flags).toContain("NEXT_PUBLIC_OMNISEARCH_ENABLED");
    expect(chat).toContain("{omnisearchEnabled && searchOverlayOpen && (");
    expect(sidebar).toContain("strategiesEnabled");
    expect(sidebar).toContain("omnisearchEnabled");
    expect(sidebar).toContain("{omnisearchEnabled && (");
    expect(sidebar).toContain("{strategiesEnabled && (");
    expect(sidebar).toContain("common.recents");
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
