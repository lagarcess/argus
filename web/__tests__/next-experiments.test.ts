import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  NEXT_EXPERIMENTS_VERSION,
  nextExperimentAction,
  nextExperimentRowsFromMetadata,
} from "@/lib/chat-next-experiments";

const root = join(import.meta.dir, "..");
const en = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
);
const es = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
);

const row = {
  kind: "change_date_range",
  label: "Change the date range",
  label_key: "chat.next_experiments.labels.change_date_range",
  why: { code: "beat_benchmark", params: { points: 4.2 } },
};

describe("Try next rows (issue #249)", () => {
  test("rows project only from the typed versioned sidecar", () => {
    expect(
      nextExperimentRowsFromMetadata({
        next_experiments: { version: NEXT_EXPERIMENTS_VERSION, rows: [row] },
      }),
    ).toEqual([
      {
        kind: "change_date_range",
        label: "Change the date range",
        labelKey: "chat.next_experiments.labels.change_date_range",
        why: { code: "beat_benchmark", params: { points: 4.2 } },
        detail: null,
        sendText: null,
        labelShort: null,
        labelShortKey: null,
        labelParts: null,
      },
    ]);
    expect(
      nextExperimentRowsFromMetadata({
        next_experiments: { version: "unknown/v9", rows: [row] },
      }),
    ).toBeNull();
    expect(nextExperimentRowsFromMetadata({})).toBeNull();
    expect(
      nextExperimentRowsFromMetadata({
        next_experiments: { version: NEXT_EXPERIMENTS_VERSION, rows: [{}] },
      }),
    ).toBeNull();
  });

  test("rows cap at three even if the backend misbehaves", () => {
    const many = Array.from({ length: 6 }, (_, index) => ({
      ...row,
      kind: `kind_${index}`,
      label_key: `chat.next_experiments.labels.kind_${index}`,
    }));
    const rows = nextExperimentRowsFromMetadata({
      next_experiments: { version: NEXT_EXPERIMENTS_VERSION, rows: many },
    });
    expect(rows).toHaveLength(3);
  });

  test("issue 345 recommendations carry their source run as typed refinements", () => {
    const action = nextExperimentAction(
      {
        kind: "change_date_range",
        label: "Change the date range",
        labelKey: "chat.next_experiments.labels.change_date_range",
        why: null,
      },
      "Cambiar el rango de fechas",
      "run-345-source",
    );
    expect(action.type).toBe("refine_strategy");
    expect(action.presentation).toBe("result");
    expect(action.payload).toEqual({
      run_id: "run-345-source",
      next_experiment_kind: "change_date_range",
    });
    expect(action.label).toBe("Cambiar el rango de fechas");
    expect(action.value).toBe("Cambiar el rango de fechas");
  });

  test("unrelated recommendation kinds keep the ordinary turn path", () => {
    const action = nextExperimentAction(
      {
        kind: "same_setup_peer_asset",
        label: "Test a similar asset",
        labelKey: "chat.next_experiments.labels.same_setup_peer_asset",
        why: null,
      },
      "Test a similar asset",
      "run-345-source",
    );
    expect(action.type).toBeUndefined();
    expect(action.payload).toBeUndefined();
  });

  test("every experiment kind is localized in both languages", () => {
    const kinds = [
      "change_date_range",
      "same_setup_peer_asset",
      "same_rule_peer_asset",
      "supported_rsi_threshold",
      "recurring_monthly_buys",
      "supported_ma_crossover",
      "supported_rsi_or_ma_rule",
      "adjust_indicator_thresholds",
      "adjust_signal_periods",
      "adjust_contribution_cadence",
      "compare_buy_and_hold",
    ];
    for (const kind of kinds) {
      expect(en.chat.next_experiments.labels[kind]).toBeTruthy();
      expect(es.chat.next_experiments.labels[kind]).toBeTruthy();
    }
    expect(en.chat.next_experiments.section).toBe("Try next");
    expect(es.chat.next_experiments.section).toBeTruthy();
    for (const code of ["lost_to_benchmark", "beat_benchmark", "deep_drawdown"]) {
      expect(en.chat.next_experiments.why[code]).toContain("{{");
      expect(es.chat.next_experiments.why[code]).toContain("{{");
    }
  });

  test("the message surface renders the Try next section and the failure treatment", () => {
    const source = readFileSync(
      join(root, "components/chat/ChatMessage.tsx"),
      "utf-8",
    );
    expect(source).toContain(
      'aria-label={t("chat.next_experiments.section", "Try next")}',
    );
    // Infrastructure failure renders as visibly-a-failure, never under
    // result chrome.
    expect(source).toContain("message.assistantRecoveryCode ? (");
    const failureBranch = source.slice(
      source.indexOf("message.assistantRecoveryCode ? ("),
      source.indexOf('role="status"'),
    );
    expect(failureBranch).not.toContain("factHeadingLabel");
  });
});

describe("ticker badges on suggestion rows", () => {
  test("typed label parts survive projection and keep a plain-text label", () => {
    const rows = nextExperimentRowsFromMetadata({
      next_experiments: {
        version: NEXT_EXPERIMENTS_VERSION,
        rows: [
          {
            kind: "research_test_single",
            label: "Test Netflix (NFLX) over the last 3 years",
            label_key: "chat.next_experiments.labels.research_dynamic",
            label_parts: [
              { type: "text", value: "Test " },
              { type: "text", value: "Netflix" },
              { type: "ticker", value: "NFLX" },
              { type: "text", value: " over the last 3 years" },
            ],
          },
        ],
      },
    });
    expect(rows?.[0].labelParts).toEqual([
      { type: "text", value: "Test " },
      { type: "text", value: "Netflix" },
      { type: "ticker", value: "NFLX" },
      { type: "text", value: " over the last 3 years" },
    ]);
    // The plain label stays the sentence the badge row shows, so aria labels
    // and analytics read the same thing the eye does.
    expect(rows?.[0].label).toBe("Test Netflix (NFLX) over the last 3 years");
  });

  test("malformed or empty parts degrade to the plain label", () => {
    const rows = nextExperimentRowsFromMetadata({
      next_experiments: {
        version: NEXT_EXPERIMENTS_VERSION,
        rows: [
          {
            kind: "research_test_single",
            label: "Test Netflix (NFLX) over the last 3 years",
            label_key: "chat.next_experiments.labels.research_dynamic",
            label_parts: [{ type: "text", value: "" }, "nonsense", 7],
          },
        ],
      },
    });
    expect(rows?.[0].labelParts).toBeNull();
    expect(rows?.[0].label).toBe("Test Netflix (NFLX) over the last 3 years");
  });
});

describe("research citations reach the live turn", () => {
  test("the stream path attaches typed sources, not only hydration", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    // A turn that cited pages must offer them when it lands, not after a
    // reload: the panel is fed from the final payload too.
    expect(chat).toContain("researchSourcesForFinalPayload(finalPayload)");
    expect(chat).toContain("researchSources: finalResearchSources");
    const merge = readFileSync(
      join(import.meta.dir, "../lib/chat-final-message.ts"),
      "utf-8",
    );
    expect(merge).toContain("researchSources ?? message.researchSources");
  });
});
