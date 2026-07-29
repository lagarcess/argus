import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { confirmationBenchmarkAdjustmentText } from "@/lib/confirmation-benchmark-adjustment";

const root = join(import.meta.dir, "..");
const en = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
);
const es = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
);

function tFrom(catalog: Record<string, any>) {
  return (key: string, options: { target: string; benchmark: string }) => {
    const template = key
      .split(".")
      .reduce((node: any, part) => node?.[part], catalog) as string;
    return template
      .replace("{{target}}", options.target)
      .replace("{{benchmark}}", options.benchmark);
  };
}

describe("confirmation benchmark adjustment (#296)", () => {
  test("renders the reconciliation note in both languages", () => {
    const adjustment = {
      code: "comparison_target_unsupported",
      requested_target: "SAMSUNG",
      effective_benchmark: "SPY",
    };
    expect(confirmationBenchmarkAdjustmentText(adjustment, tFrom(en))).toBe(
      "SAMSUNG isn't available from our data provider, so this compares against SPY instead.",
    );
    expect(confirmationBenchmarkAdjustmentText(adjustment, tFrom(es))).toBe(
      "SAMSUNG no está disponible en nuestro proveedor de datos, así que la comparación es contra SPY.",
    );
  });

  test("unknown codes and empty fields render nothing", () => {
    expect(
      confirmationBenchmarkAdjustmentText(
        { code: "other", requested_target: "X", effective_benchmark: "SPY" },
        tFrom(en),
      ),
    ).toBeNull();
    expect(
      confirmationBenchmarkAdjustmentText(
        {
          code: "comparison_target_unsupported",
          requested_target: " ",
          effective_benchmark: "SPY",
        },
        tFrom(en),
      ),
    ).toBeNull();
    expect(confirmationBenchmarkAdjustmentText(undefined, tFrom(en))).toBeNull();
  });

  test("the note is pinned above the card like the period adjustment", () => {
    const chat = readFileSync(
      join(root, "components/chat/ChatMessage.tsx"),
      "utf-8",
    );
    expect(chat).toContain("confirmationBenchmarkLeadIn");
    expect(chat.indexOf("{confirmationBenchmarkLeadIn ? (")).toBeGreaterThan(
      chat.indexOf("{confirmationPeriodLeadIn ? ("),
    );
    expect(chat.indexOf("{confirmationBenchmarkLeadIn ? (")).toBeLessThan(
      chat.indexOf("<StrategyConfirmationCard"),
    );
  });
});
