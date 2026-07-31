import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Message, StrategyResultPayload } from "@/components/chat/types";
import type { BacktestJob } from "@/lib/argus-api";
import {
  conversationRailVisible,
  deriveConversationRailTicks,
  INITIAL_RAIL_DWELL_STATE,
  RAIL_MIN_TICKS,
  RAIL_MIN_TRANSCRIPT_MESSAGES,
  RAIL_PREVIEW_DWELL_MS,
  RAIL_PROXIMITY_RADIUS_PX,
  RAIL_TICK_MAGNET_RADIUS_PX,
  RAIL_TICK_STACK_PITCH_PX,
  railDwellReducer,
  railRevealProgress,
  railTickExtension,
  railTickStackOffsetPx,
} from "@/lib/conversation-rail";

const root = join(import.meta.dir, "..");

function textMessage(
  id: string,
  role: "user" | "ai",
  extra: Partial<Message> = {},
): Message {
  return { id, role, kind: "text", content: `content-${id}`, ...extra };
}

function resultPayload(
  extra: Partial<StrategyResultPayload> = {},
): StrategyResultPayload {
  return {
    strategyName: "DCA BTC",
    strategyLabel: "DCA — BTC weekly",
    symbols: ["BTC", "ETH"],
    period: "2020 – 2024",
    metrics: [
      { label: "Total return", value: "+120%" },
      { label: "CAGR", value: "17.1%" },
      { label: "Max drawdown", value: "-32%" },
      { label: "Sharpe", value: "0.9" },
    ],
    ...extra,
  };
}

function resultMessage(
  id: string,
  extra: Partial<StrategyResultPayload> = {},
  messageExtra: Partial<Message> = {},
): Message {
  return {
    id,
    role: "ai",
    kind: "strategy_result",
    result: resultPayload(extra),
    ...messageExtra,
  };
}

function jobMessage(id: string, status: BacktestJob["status"]): Message {
  return {
    id,
    role: "ai",
    kind: "backtest_job",
    backtestJob: {
      id: `job-${id}`,
      conversation_id: "c1",
      status,
      retryable: false,
    } as BacktestJob,
  };
}

describe("conversation rail tick derivation", () => {
  test("derives typed ticks from existing turn payloads only", () => {
    const messages: Message[] = [
      textMessage("u1", "user"),
      textMessage("a1", "ai"),
      resultMessage("a2"),
      textMessage("u2", "user"),
      resultMessage("a3", { decisionState: "promising" }),
      textMessage("a4", "ai", {
        recoveryDisplay: { kind: "coverage_recovery", code: "partial_window" },
      }),
      jobMessage("a5", "failed"),
      jobMessage("a6", "running"),
      textMessage("u3", "user", {
        recoveryDisplay: { kind: "coverage_recovery", code: "partial_window" },
      }),
      resultMessage("a7", {}, { isLoadingResult: true }),
      textMessage("a8", "ai", { assistantRecoveryCode: "compose_failed" }),
      textMessage("a9", "ai", {
        contentPresentation: "superseded_runtime_failure",
      }),
    ];

    const ticks = deriveConversationRailTicks(messages);
    expect(ticks.map((tick) => [tick.messageId, tick.kind])).toEqual([
      ["a2", "backtest_completed"],
      ["a3", "decision_saved"],
      ["a4", "error_recovery"],
      ["a5", "error_recovery"],
      ["a8", "error_recovery"],
      ["a9", "error_recovery"],
    ]);

    const backtestTick = ticks[0];
    expect(backtestTick.strategyTitle).toBe("DCA — BTC weekly");
    expect(backtestTick.symbols).toEqual(["BTC", "ETH"]);
    expect(backtestTick.periodDisplay).toBe("2020 – 2024");
    expect(backtestTick.metrics).toHaveLength(3);
    expect(backtestTick.messageIndex).toBe(2);

    const recoveryTicksCarryNoSymbols = ticks
      .filter((tick) => tick.kind === "error_recovery")
      .every((tick) => tick.symbols.length === 0);
    expect(recoveryTicksCarryNoSymbols).toBe(true);

    const decisionTick = ticks[1];
    expect(decisionTick.decisionState).toBe("promising");

    const jobTick = ticks[3];
    expect(jobTick.failedJobStatus).toBe("failed");

    const recoveryTick = ticks[2];
    expect(recoveryTick.recovery).toEqual({
      kind: "coverage_recovery",
      code: "partial_window",
    });
  });

  test("prefers dateRange.display and falls back through result fields", () => {
    const ticks = deriveConversationRailTicks([
      resultMessage("a1", {
        dateRange: { start: "2020-01-01", end: "2024-01-01", display: "Jan 2020 – Jan 2024" },
      }),
    ]);
    expect(ticks[0].periodDisplay).toBe("Jan 2020 – Jan 2024");
  });

  test("ignores plain turns so ticks stay a small fixed taxonomy", () => {
    const messages: Message[] = [
      textMessage("u1", "user"),
      textMessage("a1", "ai"),
      textMessage("a2", "ai"),
    ];
    expect(deriveConversationRailTicks(messages)).toEqual([]);
  });
});

describe("conversation rail visibility threshold", () => {
  test("only long conversations with enough ticks earn the rail", () => {
    expect(
      conversationRailVisible(RAIL_MIN_TRANSCRIPT_MESSAGES - 1, 5),
    ).toBe(false);
    expect(
      conversationRailVisible(RAIL_MIN_TRANSCRIPT_MESSAGES, RAIL_MIN_TICKS - 1),
    ).toBe(false);
    expect(
      conversationRailVisible(RAIL_MIN_TRANSCRIPT_MESSAGES, RAIL_MIN_TICKS),
    ).toBe(true);
  });
});

describe("proximity reveal ramp", () => {
  test("reveal ramps with distance instead of firing on contact", () => {
    expect(railRevealProgress(RAIL_PROXIMITY_RADIUS_PX)).toBe(0);
    expect(railRevealProgress(RAIL_PROXIMITY_RADIUS_PX * 2)).toBe(0);
    expect(railRevealProgress(Number.POSITIVE_INFINITY)).toBe(0);
    expect(railRevealProgress(0)).toBe(1);
    expect(railRevealProgress(-4)).toBe(1);
    const half = railRevealProgress(RAIL_PROXIMITY_RADIUS_PX / 2);
    expect(half).toBeGreaterThan(0.45);
    expect(half).toBeLessThan(0.55);
    expect(railRevealProgress(40)).toBeLessThan(railRevealProgress(10));
  });
});

describe("dwell gating", () => {
  test("first contact never opens a preview", () => {
    const state = railDwellReducer(INITIAL_RAIL_DWELL_STATE, {
      type: "tick_enter",
      tickId: "m1",
      at: 1_000,
    });
    expect(state.openTickId).toBeNull();
    const early = railDwellReducer(state, {
      type: "elapse",
      at: 1_000 + RAIL_PREVIEW_DWELL_MS - 1,
    });
    expect(early.openTickId).toBeNull();
  });

  test("preview opens only after the dwell threshold", () => {
    let state = railDwellReducer(INITIAL_RAIL_DWELL_STATE, {
      type: "tick_enter",
      tickId: "m1",
      at: 1_000,
    });
    state = railDwellReducer(state, {
      type: "elapse",
      at: 1_000 + RAIL_PREVIEW_DWELL_MS,
    });
    expect(state.openTickId).toBe("m1");
  });

  test("leaving before the dwell threshold cancels the pending preview", () => {
    let state = railDwellReducer(INITIAL_RAIL_DWELL_STATE, {
      type: "tick_enter",
      tickId: "m1",
      at: 1_000,
    });
    state = railDwellReducer(state, { type: "tick_leave" });
    state = railDwellReducer(state, {
      type: "elapse",
      at: 1_000 + RAIL_PREVIEW_DWELL_MS * 4,
    });
    expect(state.openTickId).toBeNull();
  });

  test("cold crossing between ticks stays closed until a dwell lands", () => {
    let state = railDwellReducer(INITIAL_RAIL_DWELL_STATE, {
      type: "tick_enter",
      tickId: "m1",
      at: 1_000,
    });
    state = railDwellReducer(state, { type: "tick_leave" });
    state = railDwellReducer(state, {
      type: "tick_enter",
      tickId: "m2",
      at: 1_050,
    });
    expect(state.openTickId).toBeNull();
    state = railDwellReducer(state, { type: "elapse", at: 1_060 });
    expect(state.openTickId).toBeNull();
    state = railDwellReducer(state, {
      type: "elapse",
      at: 1_050 + RAIL_PREVIEW_DWELL_MS,
    });
    expect(state.openTickId).toBe("m2");
  });

  test("gliding with a preview open switches ticks instantly", () => {
    let state = railDwellReducer(INITIAL_RAIL_DWELL_STATE, {
      type: "tick_enter",
      tickId: "m1",
      at: 1_000,
    });
    state = railDwellReducer(state, {
      type: "elapse",
      at: 1_000 + RAIL_PREVIEW_DWELL_MS,
    });
    expect(state.openTickId).toBe("m1");
    state = railDwellReducer(state, { type: "tick_leave" });
    expect(state.openTickId).toBe("m1");
    state = railDwellReducer(state, {
      type: "tick_enter",
      tickId: "m2",
      at: 2_000,
    });
    expect(state.openTickId).toBe("m2");
    state = railDwellReducer(state, { type: "rail_exit" });
    expect(state).toEqual(INITIAL_RAIL_DWELL_STATE);
  });

  test("leaving the rail resets everything; focus opens deliberately", () => {
    let state = railDwellReducer(INITIAL_RAIL_DWELL_STATE, {
      type: "focus_open",
      tickId: "m3",
    });
    expect(state.openTickId).toBe("m3");
    state = railDwellReducer(state, { type: "rail_exit" });
    expect(state).toEqual(INITIAL_RAIL_DWELL_STATE);
  });
});

describe("rail tick stack", () => {
  test("ticks form a fixed-pitch queue centered on the rail", () => {
    expect(railTickStackOffsetPx(0, 1)).toBe(0);
    expect(railTickStackOffsetPx(0, 3)).toBe(-RAIL_TICK_STACK_PITCH_PX);
    expect(railTickStackOffsetPx(1, 3)).toBe(0);
    expect(railTickStackOffsetPx(2, 3)).toBe(RAIL_TICK_STACK_PITCH_PX);
    for (let i = 1; i < 8; i += 1) {
      expect(railTickStackOffsetPx(i, 8) - railTickStackOffsetPx(i - 1, 8)).toBe(
        RAIL_TICK_STACK_PITCH_PX,
      );
    }
  });

  test("spacing never encodes transcript distance", () => {
    const nearMessages: Message[] = [
      resultMessage("a1"),
      resultMessage("a2"),
    ];
    const farMessages: Message[] = [
      resultMessage("b1"),
      ...Array.from({ length: 48 }, (_, i) => textMessage(`t${i}`, "ai")),
      resultMessage("b2"),
    ];
    const near = deriveConversationRailTicks(nearMessages);
    const far = deriveConversationRailTicks(farMessages);
    expect(railTickStackOffsetPx(1, near.length) - railTickStackOffsetPx(0, near.length)).toBe(
      railTickStackOffsetPx(1, far.length) - railTickStackOffsetPx(0, far.length),
    );
  });
});

describe("per-tick magnetization", () => {
  test("extension peaks under the pointer and falls off over neighbors", () => {
    expect(railTickExtension(0)).toBe(1);
    expect(railTickExtension(-3)).toBe(1);
    expect(railTickExtension(RAIL_TICK_MAGNET_RADIUS_PX)).toBe(0);
    expect(railTickExtension(Number.POSITIVE_INFINITY)).toBe(0);
    const neighbor = railTickExtension(RAIL_TICK_STACK_PITCH_PX);
    const nextNeighbor = railTickExtension(RAIL_TICK_STACK_PITCH_PX * 2);
    expect(neighbor).toBeGreaterThan(0);
    expect(neighbor).toBeLessThan(1);
    expect(nextNeighbor).toBeLessThan(neighbor);
  });
});

describe("rail source discipline", () => {
  const componentSource = readFileSync(
    join(root, "components/chat/ConversationActivityRail.tsx"),
    "utf-8",
  );
  const libSource = readFileSync(join(root, "lib/conversation-rail.ts"), "utf-8");
  const anchorSource = readFileSync(
    join(root, "components/chat/useTranscriptTurnAnchor.ts"),
    "utf-8",
  );
  const interfaceSource = readFileSync(
    join(root, "components/chat/ChatInterface.tsx"),
    "utf-8",
  );

  test("rail makes zero backend or provider calls", () => {
    for (const source of [componentSource, libSource, anchorSource]) {
      expect(source).not.toContain("fetch(");
      expect(source).not.toContain("streamChatMessage");
      expect(source).not.toContain("openrouter");
      expect(source).not.toContain("http://");
      expect(source).not.toContain("https://");
    }
    expect(componentSource).not.toContain("argus-api");
    expect(libSource).toMatch(
      /import type \{ DecisionState \} from "@\/lib\/argus-api"/,
    );
  });

  test("hover preview is dwell-gated, never instant on pointer contact", () => {
    expect(componentSource).toContain("railDwellReducer");
    expect(componentSource).toMatch(
      /onPointerEnter=\{\(\) => handleTickEnter\(tick\.messageId\)\}/,
    );
    expect(componentSource).toContain("RAIL_PREVIEW_DWELL_MS + 20");
    expect(componentSource).not.toMatch(/onPointerEnter[^\n]*focus_open/);
    expect(componentSource).not.toMatch(/onPointerEnter[^\n]*elapse/);
  });

  test("rail wakes on proximity via the reveal ramp", () => {
    expect(componentSource).toContain("railRevealProgress");
    expect(componentSource).toContain("--rail-reveal");
    expect(componentSource).toContain("data-rail-awake");
  });

  test("ticks stack at fixed pitch and magnetize individually", () => {
    expect(componentSource).toContain("railTickStackOffsetPx");
    expect(componentSource).toContain("railTickExtension");
    expect(componentSource).toContain("--tick-extend");
    expect(componentSource).toContain("calc(50% + ${offsets[index]}px)");
    expect(componentSource).not.toContain("railTickOffsets");
  });

  test("rail sits on the right edge and hides on small screens", () => {
    expect(componentSource).toMatch(/absolute bottom-40 right-0 top-24/);
    expect(componentSource).toContain("hidden md:block");
  });

  test("preview and aria carry run symbols for identity during a glide", () => {
    expect(componentSource).toContain("openTick.symbols.join(\" · \")");
    expect(componentSource).toMatch(
      /\[tick\.symbols\[0\], tick\.strategyTitle\]/,
    );
  });

  test("preview popover is a passive preview, not an action surface", () => {
    expect(componentSource).toContain("pointer-events-none absolute right-[calc(100%+10px)]");
    const previewBlock = componentSource.slice(
      componentSource.indexOf("conversation-activity-rail-preview"),
    );
    expect(previewBlock).not.toContain("<button");
    expect(previewBlock).not.toContain("onClick");
  });

  test("chat interface mounts the rail and jumps within the same transcript", () => {
    expect(interfaceSource).toContain("<ConversationActivityRail");
    expect(interfaceSource).toContain("onSelectTick={anchorToTurn}");
    expect(interfaceSource).toContain("useTranscriptTurnAnchor({");
    expect(interfaceSource).not.toContain("deriveConversationRailTicks");
    expect(componentSource).toContain("deriveConversationRailTicks(messages)");
    expect(anchorSource).toMatch(
      /anchorToTurn[\s\S]{0,300}messageElementRefs\.current\.get\(messageId\)[\s\S]{0,200}scrollIntoView\(\{ block: "center", behavior: "smooth" \}\)/,
    );
  });
});

describe("rail localization", () => {
  const en = JSON.parse(
    readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
  ) as { chat: { activity_rail: Record<string, string> } };
  const es = JSON.parse(
    readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
  ) as { chat: { activity_rail: Record<string, string> } };

  test("EN and es-419 ship the same non-empty activity rail keys", () => {
    const enKeys = Object.keys(en.chat.activity_rail).sort();
    const esKeys = Object.keys(es.chat.activity_rail).sort();
    expect(enKeys).toEqual([
      "aria_label",
      "backtest_completed",
      "jump_hint",
      "needs_attention",
      "needs_attention_body",
    ]);
    expect(esKeys).toEqual(enKeys);
    for (const key of enKeys) {
      expect(en.chat.activity_rail[key].trim().length).toBeGreaterThan(0);
      expect(es.chat.activity_rail[key].trim().length).toBeGreaterThan(0);
    }
    expect(es.chat.activity_rail.aria_label).not.toBe(
      en.chat.activity_rail.aria_label,
    );
  });
});
