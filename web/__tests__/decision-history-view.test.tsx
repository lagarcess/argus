import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import {
  DecisionHistoryView,
  attemptDecisionHistoryListboxFocus,
  decisionHistoryKeyboardAction,
} from "../components/sidebar/command-palette/DecisionHistoryView";
import type { RunDossier } from "../lib/run-dossier-contract";

function dossier(
  runId: string,
  completedAt: string,
  decision: RunDossier["decision"],
): RunDossier {
  return {
    run_id: runId,
    run_label: `Run ${runId}`,
    completed_at: completedAt,
    result_message_id: `message-${runId}`,
    tested: {
      symbols: ["GLD"],
      strategy_family: "buy_and_hold",
      cadence: null,
      timeframe: "1D",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
    },
    outcome: {
      run_label: `Run ${runId}`,
      completed_at: completedAt,
      benchmark_symbol: "SPY",
      quick_take: null,
      metrics: [],
    },
    decision,
    actions: [],
  };
}

const newest = dossier("newest", "2026-07-31T14:30:00.000Z", {
  state: "watching",
  note: "Hold through earnings.\nReview risk first.",
  run_label: "Run newest",
});
const middle = dossier("middle", "2026-06-18T14:30:00.000Z", {
  state: "rejected",
  note: "Drawdown was too high.",
  run_label: "Run middle",
});
const oldest = dossier("oldest", "2026-05-02T14:30:00.000Z", null);

function visibleText(html: string): string {
  return html
    .replace(
      /<span[^>]*class="[^"]*sr-only[^"]*"[^>]*>[\s\S]*?<\/span>/g,
      "",
    )
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

describe("decision history view", () => {
  test("renders newest-first rows with one current decision unit per run", () => {
    const html = renderToStaticMarkup(
      <DecisionHistoryView
        items={[newest, middle, oldest]}
        nextCursor="older-cursor"
        status="ready"
        onBack={() => {}}
        onLoadOlder={() => {}}
        onRetry={() => {}}
        onSelectRun={() => {}}
      />,
    );
    const text = visibleText(html);

    expect(text).not.toContain("Dossier");
    expect(html).toMatch(
      /<button[^>]*aria-label="Back to run details"[^>]*class="[^"]*h-11[^"]*w-11/,
    );
    expect(text).toContain("Decision history");
    expect(text.indexOf("Run newest")).toBeLessThan(text.indexOf("Run middle"));
    expect(text.indexOf("Run middle")).toBeLessThan(text.indexOf("Run oldest"));
    expect(text.match(/Watching/g)).toHaveLength(1);
    expect(text.match(/Rejected/g)).toHaveLength(1);
    expect(text.match(/No decision saved/g)).toHaveLength(1);
    expect(html).toContain("Hold through earnings.\nReview risk first.");
    expect(html).toContain("whitespace-pre-wrap");
    expect(text).toContain("Load older");
    expect(html).toContain('aria-activedescendant="decision-history-run-newest"');
  });

  test("shows bounded loading, error, retry, and loaded-row preservation states", () => {
    const loading = visibleText(
      renderToStaticMarkup(
        <DecisionHistoryView
          items={[]}
          nextCursor={null}
          status="loading"
          onBack={() => {}}
          onLoadOlder={() => {}}
          onRetry={() => {}}
          onSelectRun={() => {}}
        />,
      ),
    );
    const erroredHtml = renderToStaticMarkup(
      <DecisionHistoryView
        items={[newest]}
        nextCursor="older-cursor"
        status="error"
        onBack={() => {}}
        onLoadOlder={() => {}}
        onRetry={() => {}}
        onSelectRun={() => {}}
      />,
    );
    const errored = visibleText(erroredHtml);
    const refreshing = visibleText(
      renderToStaticMarkup(
        <DecisionHistoryView
          items={[newest]}
          nextCursor={null}
          status="loading"
          onBack={() => {}}
          onLoadOlder={() => {}}
          onRetry={() => {}}
          onSelectRun={() => {}}
        />,
      ),
    );

    expect(loading).toContain("Loading decision history");
    expect(refreshing).toContain("Run newest");
    expect(refreshing).toContain("Loading decision history");
    expect(errored).toContain("Run newest");
    expect(errored).toContain("Could not load decision history");
    expect(errored).toContain("Try again");
    expect(errored).not.toContain("Retry");
    expect(erroredHtml).not.toContain(">Load older<");
  });

  test("exposes a pure bounded keyboard contract without navigation behavior", () => {
    expect(
      decisionHistoryKeyboardAction({ key: "ArrowDown", activeIndex: 0, count: 3 }),
    ).toEqual({ activeIndex: 1, selectedIndex: null, back: false, handled: true });
    expect(
      decisionHistoryKeyboardAction({ key: "ArrowDown", activeIndex: 2, count: 3 }),
    ).toEqual({ activeIndex: 2, selectedIndex: null, back: false, handled: true });
    expect(
      decisionHistoryKeyboardAction({ key: "ArrowUp", activeIndex: 0, count: 3 }),
    ).toEqual({ activeIndex: 0, selectedIndex: null, back: false, handled: true });
    expect(
      decisionHistoryKeyboardAction({ key: "Enter", activeIndex: 1, count: 3 }),
    ).toEqual({ activeIndex: 1, selectedIndex: 1, back: false, handled: true });
    expect(
      decisionHistoryKeyboardAction({ key: " ", activeIndex: 1, count: 3 }),
    ).toEqual({ activeIndex: 1, selectedIndex: 1, back: false, handled: true });
    expect(
      decisionHistoryKeyboardAction({ key: "Escape", activeIndex: 1, count: 3 }),
    ).toEqual({ activeIndex: 1, selectedIndex: null, back: true, handled: true });
    expect(
      decisionHistoryKeyboardAction({ key: "Enter", activeIndex: 0, count: 0 }),
    ).toEqual({ activeIndex: 0, selectedIndex: null, back: false, handled: false });
    expect(
      decisionHistoryKeyboardAction({ key: "Tab", activeIndex: 1, count: 3 }),
    ).toEqual({ activeIndex: 1, selectedIndex: null, back: false, handled: false });
  });

  test("focuses and consumes the first ready history attempt from BODY", () => {
    let focusCalls = 0;
    let focusOptions: FocusOptions | undefined;
    const body = {};
    const listbox = {
      ownerDocument: { activeElement: body, body },
      focus(options?: FocusOptions) {
        focusCalls += 1;
        focusOptions = options;
      },
    };

    expect(
      attemptDecisionHistoryListboxFocus({
        listbox,
        status: "ready",
        itemCount: 3,
        hasAttempted: false,
      }),
    ).toBe(true);
    expect(focusCalls).toBe(1);
    expect(focusOptions).toEqual({ preventScroll: true });
  });

  test("consumes the first ready attempt without stealing deliberate focus", () => {
    let focusCalls = 0;
    const body = {};
    const deliberateTarget = {};
    const ownerDocument = { activeElement: deliberateTarget, body };
    const listbox = {
      ownerDocument,
      focus() {
        focusCalls += 1;
      },
    };

    const skipped = attemptDecisionHistoryListboxFocus({
      listbox,
      status: "ready",
      itemCount: 3,
      hasAttempted: false,
    });

    expect(skipped).toBe(true);
    expect(focusCalls).toBe(0);

    ownerDocument.activeElement = body;
    expect(
      attemptDecisionHistoryListboxFocus({
        listbox,
        status: "ready",
        itemCount: 3,
        hasAttempted: skipped,
      }),
    ).toBe(false);
    expect(focusCalls).toBe(0);
  });

  test("does not consume the focus attempt before ready non-empty history", () => {
    let focusCalls = 0;
    const body = {};
    const listbox = {
      ownerDocument: { activeElement: body, body },
      focus() {
        focusCalls += 1;
      },
    };

    expect(
      attemptDecisionHistoryListboxFocus({
        listbox,
        status: "loading",
        itemCount: 3,
        hasAttempted: false,
      }),
    ).toBe(false);
    expect(
      attemptDecisionHistoryListboxFocus({
        listbox,
        status: "ready",
        itemCount: 0,
        hasAttempted: false,
      }),
    ).toBe(false);
    expect(
      attemptDecisionHistoryListboxFocus({
        listbox,
        status: "ready",
        itemCount: 3,
        hasAttempted: true,
      }),
    ).toBe(false);
    expect(focusCalls).toBe(0);
  });

  test("renders the listbox keyboard target so ArrowDown then Enter selects the second run", () => {
    const html = renderToStaticMarkup(
      <DecisionHistoryView
        items={[newest, middle, oldest]}
        nextCursor={null}
        status="ready"
        onBack={() => {}}
        onLoadOlder={() => {}}
        onRetry={() => {}}
        onSelectRun={() => {}}
      />,
    );
    const moved = decisionHistoryKeyboardAction({
      key: "ArrowDown",
      activeIndex: 0,
      count: 3,
    });
    const selected = decisionHistoryKeyboardAction({
      key: "Enter",
      activeIndex: moved.activeIndex,
      count: 3,
    });

    expect(html).toContain('role="listbox"');
    expect(selected.selectedIndex).toBe(1);
  });
});
