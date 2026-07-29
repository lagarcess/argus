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

  test("a tapped row sends its localized label as an ordinary turn", () => {
    const action = nextExperimentAction(
      {
        kind: "change_date_range",
        label: "Change the date range",
        labelKey: "chat.next_experiments.labels.change_date_range",
        why: null,
      },
      "Cambiar el rango de fechas",
    );
    // No type: the plain send path carries the label as the user's turn.
    expect(action.type).toBeUndefined();
    expect(action.payload).toBeUndefined();
    expect(action.label).toBe("Cambiar el rango de fechas");
    expect(action.value).toBe("Cambiar el rango de fechas");
  });

  test("every experiment kind is localized in both languages", () => {
    const kinds = [
      "change_date_range",
      "same_setup_peer_asset",
      "same_rule_peer_asset",
      "supported_rsi_threshold",
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
    expect(source).toContain("nextExperimentAction(row, rowLabel)");
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
