import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import {
  DecisionEditor,
  decisionEditorKeyboardAction,
} from "../components/sidebar/command-palette/DecisionEditor";
import { decisionNoteElementOverflows } from "../components/sidebar/command-palette/DecisionNoteDisplay";
import {
  resolveDecisionSaveLifecycle,
  RunDossierView,
} from "../components/sidebar/command-palette/RunDossierView";
import { refreshCanonicalMutation } from "../lib/canonical-mutation-refresh";
import type {
  RunDossier,
  SearchDecisionAction,
} from "../lib/run-dossier-contract";

const decisionAction: SearchDecisionAction = {
  type: "decision",
  evidence_artifact_id: "evidence-7",
  decision_state: "watching",
  note: "Hold through earnings.\nReview risk first.",
  run_label: "Weekly GLD pullback",
};

const dossierWithWatchingDecisionAndMultilineNote: RunDossier = {
  run_id: "run-7",
  run_label: "Weekly GLD pullback",
  completed_at: "2026-07-31T14:30:00.000Z",
  result_message_id: "message-7",
  tested: {
    symbols: ["GLD"],
    strategy_family: "buy_and_hold",
    cadence: "weekly",
    timeframe: "1D",
    start_date: "2025-01-01",
    end_date: "2025-12-31",
  },
  outcome: {
    run_label: "Weekly GLD pullback",
    completed_at: "2026-07-31T14:30:00.000Z",
    benchmark_symbol: "SPY",
    quick_take: "GLD held up better than SPY.",
    metrics: [
      { name: "total_return_pct", value: 8.4 },
      { name: "benchmark_return_pct", value: 6.1 },
      { name: "delta_vs_benchmark_pct", value: 2.3 },
      { name: "max_drawdown_pct", value: -6.2 },
    ],
  },
  decision: {
    state: "watching",
    note: "Hold through earnings.\nReview risk first.",
    run_label: "Weekly GLD pullback",
  },
  actions: [
    {
      type: "run_fresh",
      source_run_id: "run-7",
      run_label: "Weekly GLD pullback",
      canonical_setup: {
        strategy_type: "buy_and_hold",
        symbols: ["GLD"],
        asset_class: "equity",
        timeframe: "1D",
        date_range: { start: "2025-01-01", end: "2025-12-31" },
        sizing_mode: "capital_amount",
        capital_amount: 10_000,
        position_size: null,
        cadence: null,
        recurring_contribution: null,
        starting_principal: null,
        benchmark_symbol: "SPY",
        entry_rule: { type: "start_of_period" },
        exit_rule: { type: "end_of_period" },
        rule_spec: null,
        parameters: {},
        execution_realism: null,
      },
      send_text: "Test this exact supported setup again.",
    },
    decisionAction,
  ],
};

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

describe("single-run dossier view", () => {
  test("makes the desktop dossier body the scroll region", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={dossierWithWatchingDecisionAndMultilineNote}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );

    expect(html).toMatch(
      /data-dossier-scroll-region="true"[^>]*class="[^"]*md:overflow-y-auto/,
    );
  });

  test("keeps all metrics in one compact separator-based definition grid", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={dossierWithWatchingDecisionAndMultilineNote}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );
    const metricsMarkup = html.match(
      /<dl[^>]*data-dossier-metrics-layout="compact"[^>]*>[\s\S]*?<\/dl>/,
    )?.[0];

    expect(metricsMarkup).toBeDefined();
    expect(metricsMarkup?.match(/<dt/g)).toHaveLength(4);
    expect(metricsMarkup?.match(/<dd/g)).toHaveLength(4);
    expect(metricsMarkup).toContain("border-l");
    expect(metricsMarkup).toContain("border-t");
    expect(metricsMarkup).not.toContain("bg-black/[0.025]");
  });

  test("shows one run decision beside its verbatim note without repeated headings", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={dossierWithWatchingDecisionAndMultilineNote}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );
    const text = visibleText(html);

    expect(text.match(/\bWatching\b/g)).toHaveLength(1);
    expect(html).toContain("Hold through earnings.\nReview risk first.");
    expect(html).toContain("whitespace-pre-wrap");
    expect(text).not.toContain("What you tested");
    expect(text).not.toContain("How it went");
    expect(html).not.toMatch(/>Decision</);
    expect(text).not.toContain("Your note");
    expect(text).toContain("Backtest");
    expect(html).not.toContain('data-decision-chip="true"');
    expect(text).toContain("5 of 7 decided");
    expect(text).toContain("Decision history");
    expect(text.lastIndexOf("Decision history")).toBeGreaterThan(
      text.lastIndexOf("Open in conversation"),
    );
    expect(text).toContain("Edit");
    expect(text).not.toContain("Change decision");
    expect(html).toMatch(/data-decision-state-row="true"/);
    expect(html).toMatch(/data-decision-edit="true"[^>]*class="[^"]*h-8/);
  });

  test("keeps a long note in panel flow behind an accessible disclosure", () => {
    const longNote = `${"Review the downside before increasing conviction. ".repeat(9)}\nNext review: after earnings.`;
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={{
          ...dossierWithWatchingDecisionAndMultilineNote,
          decision: {
            ...dossierWithWatchingDecisionAndMultilineNote.decision!,
            note: longNote,
          },
        }}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );

    expect(html).toContain(longNote);
    expect(html).toContain("Show full note");
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("line-clamp-5");
    const noteMarkup = html.match(
      /<p[^>]*data-decision-note="true"[^>]*>[\s\S]*?<\/p>/,
    )?.[0];
    expect(noteMarkup).toBeDefined();
    expect(noteMarkup).not.toContain("overflow-y-auto");
  });

  test("clamps before measuring narrow-screen note overflow", () => {
    const potentiallyWrappedNote = "Wide words can wrap on a narrow mobile dossier.";
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={{
          ...dossierWithWatchingDecisionAndMultilineNote,
          decision: {
            ...dossierWithWatchingDecisionAndMultilineNote.decision!,
            note: potentiallyWrappedNote,
          },
        }}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );

    expect(html).toMatch(/data-decision-note="true"[^>]*line-clamp-5/);
    expect(
      decisionNoteElementOverflows({ scrollHeight: 101, clientHeight: 100 }),
    ).toBeTrue();
    expect(
      decisionNoteElementOverflows({ scrollHeight: 100, clientHeight: 100 }),
    ).toBeFalse();
  });

  test("puts the existing retest action in the card header with honest copy", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={dossierWithWatchingDecisionAndMultilineNote}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );
    const text = visibleText(html);

    expect(text).toContain("Retest setup");
    expect(text).not.toContain("Run it fresh");
    expect(html.indexOf("Retest setup")).toBeLessThan(
      html.indexOf("Weekly GLD pullback"),
    );
    expect(html).toContain('data-run-fresh-location="card-header"');
  });

  test("shows one quiet undecided state and an add action", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={{
          ...dossierWithWatchingDecisionAndMultilineNote,
          decision: null,
          actions: [
            {
              ...decisionAction,
              decision_state: null,
              note: null,
            },
          ],
        }}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );
    const text = visibleText(html);

    expect(text.match(/No decision saved/g)).toHaveLength(1);
    expect(text).toContain("Add decision");
  });

  test("accessibly disables transcript navigation without a result anchor", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={{
          ...dossierWithWatchingDecisionAndMultilineNote,
          result_message_id: null,
        }}
        totalRuns={7}
        decidedRuns={5}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );

    expect(html).toMatch(
      /<button[^>]*aria-label="Open in conversation"[^>]*disabled=""/,
    );
  });

  test("uses an accessible icon-only return to the latest run", () => {
    const html = renderToStaticMarkup(
      <RunDossierView
        dossier={dossierWithWatchingDecisionAndMultilineNote}
        totalRuns={7}
        decidedRuns={5}
        onBackToLatest={() => {}}
        onOpenHistory={() => {}}
        onOpenConversation={() => {}}
        onRunFresh={() => {}}
        onSaveDecision={async () => {}}
      />,
    );

    expect(visibleText(html)).not.toContain("Dossier");
    expect(html).toMatch(
      /<button[^>]*aria-label="Back to latest run"[^>]*class="[^"]*h-11[^"]*w-11/,
    );
  });
});

describe("decision editor", () => {
  const draft = {
    state: "watching" as const,
    note: "First line\nSecond line",
  };

  test("collapses and acknowledges only after mutation and canonical refresh succeed", async () => {
    const events: string[] = [];

    const outcome = await resolveDecisionSaveLifecycle({
      draft,
      commit: async () => {
        events.push("mutation");
        await Promise.resolve();
        events.push("canonical_refresh");
      },
    });

    expect(events).toEqual(["mutation", "canonical_refresh"]);
    expect(outcome).toEqual({ draft: null, error: false, saved: true });
  });

  test("preserves the exact draft and reports error when mutation rejects", async () => {
    const events: string[] = [];

    const outcome = await resolveDecisionSaveLifecycle({
      draft,
      commit: async () => {
        events.push("mutation");
        throw new Error("mutation failed");
      },
    });

    expect(events).toEqual(["mutation"]);
    expect(outcome).toEqual({ draft, error: true, saved: false });
  });

  test("preserves the exact draft and reports error when canonical refresh rejects", async () => {
    const events: string[] = [];

    const outcome = await resolveDecisionSaveLifecycle({
      draft,
      commit: async () => {
        events.push("mutation");
        await Promise.resolve();
        events.push("canonical_refresh");
        throw new Error("canonical refresh failed");
      },
    });

    expect(events).toEqual(["mutation", "canonical_refresh"]);
    expect(outcome).toEqual({ draft, error: true, saved: false });
  });

  test("canonical refresh error treatment preserves the rejected promise", async () => {
    let readErrorWasMarked = false;
    let rejected = false;
    try {
      await refreshCanonicalMutation({
        refresh: async () => {
          throw new Error("canonical refresh failed");
        },
        onFailure: () => {
          readErrorWasMarked = true;
        },
      });
    } catch {
      rejected = true;
    }

    expect(readErrorWasMarked).toBe(true);
    expect(rejected).toBe(true);
  });

  test("reserves save and prevent-default for modified Enter", () => {
    expect(
      decisionEditorKeyboardAction({
        key: "Enter",
        metaKey: false,
        ctrlKey: false,
      }),
    ).toEqual({ save: false, preventDefault: false });
    expect(
      decisionEditorKeyboardAction({
        key: "Enter",
        metaKey: true,
        ctrlKey: false,
      }),
    ).toEqual({ save: true, preventDefault: true });
    expect(
      decisionEditorKeyboardAction({
        key: "Enter",
        metaKey: false,
        ctrlKey: true,
      }),
    ).toEqual({ save: true, preventDefault: true });
    expect(
      decisionEditorKeyboardAction({
        key: "Escape",
        metaKey: true,
        ctrlKey: false,
      }),
    ).toEqual({ save: false, preventDefault: false });
  });

  test("keeps visible cancel/save controls and preserves an errored draft", () => {
    const html = renderToStaticMarkup(
      <DecisionEditor
        action={decisionAction}
        decisionState="watching"
        note="First line\nSecond line"
        saving={false}
        error
        onDecisionStateChange={() => {}}
        onNoteChange={() => {}}
        onCancel={() => {}}
        onSave={() => {}}
      />,
    );
    const text = visibleText(html);

    expect(text).toContain("Cancel");
    expect(text).toContain("Save");
    expect(text).toContain("Something went wrong. Please try again.");
    // React's server renderer serializes a controlled textarea newline as
    // the two-character escape sequence; the controlled value is unchanged.
    expect(html).toContain("First line\\nSecond line");
  });

  test("caps authored notes at 500 characters and shows a near-limit count", () => {
    const html = renderToStaticMarkup(
      <DecisionEditor
        action={decisionAction}
        decisionState="watching"
        note={"x".repeat(480)}
        saving={false}
        error={false}
        onDecisionStateChange={() => {}}
        onNoteChange={() => {}}
        onCancel={() => {}}
        onSave={() => {}}
      />,
    );

    expect(html).not.toMatch(/<textarea[^>]*maxLength=/);
    expect(visibleText(html)).toContain("480 / 500");
  });

  test("lets a legacy long note be canceled but not resaved unchanged", () => {
    const html = renderToStaticMarkup(
      <DecisionEditor
        action={decisionAction}
        decisionState="watching"
        note={"x".repeat(501)}
        saving={false}
        error={false}
        onDecisionStateChange={() => {}}
        onNoteChange={() => {}}
        onCancel={() => {}}
        onSave={() => {}}
      />,
    );

    expect(html).toMatch(/<button[^>]*>Cancel<\/button>/);
    expect(html).not.toMatch(/<button[^>]*disabled=""[^>]*>Cancel<\/button>/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>[\s\S]*Save decision/);
    expect(visibleText(html)).toContain("501 / 500");
  });

  test("associates the decision note textarea with an explicit label", () => {
    const html = renderToStaticMarkup(
      <DecisionEditor
        action={decisionAction}
        decisionState="watching"
        note=""
        saving={false}
        error={false}
        onDecisionStateChange={() => {}}
        onNoteChange={() => {}}
        onCancel={() => {}}
        onSave={() => {}}
      />,
    );

    expect(html).toContain(
      '<label for="command-palette-decision-note" class="sr-only">Decision note</label>',
    );
    expect(html).toMatch(
      /<textarea[^>]*id="command-palette-decision-note"[^>]*placeholder="Optional note for future you"/,
    );
  });
});
