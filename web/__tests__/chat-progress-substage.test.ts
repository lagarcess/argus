import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createInstance } from "i18next";
import { parseChatStreamFrame } from "@/lib/argus-api";
import { toolProgressText } from "@/lib/tool-result-card";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const root = join(import.meta.dir, "..");

describe("actual tool-call progress", () => {
  test("legacy detail remains transport metadata without selecting user copy", () => {
    expect(parseChatStreamFrame('data: {"type":"stage_start","stage":"discovery_search","detail":"cybersecurity stocks"}')).toEqual({ event: "stage_start", data: { stage: "discovery_search", detail: "cybersecurity stocks" } });
    expect(parseChatStreamFrame('data: {"type":"stage_start","stage":"discovery_verify","detail":""}')).toEqual({ event: "stage_start", data: { stage: "discovery_verify" } });
  });

  for (const [locale, copy] of [["en", en], ["es-419", es]] as const) {
    test(`typed call arguments render in ${locale} without a model call`, async () => {
      const instance = createInstance();
      await instance.init({ lng: locale, fallbackLng: false, resources: { [locale]: { translation: copy } }, interpolation: { escapeValue: false } });
      const t = instance.t.bind(instance);
      const progress = { locale_key: "chat.tools.progress.backtest", interpolation_args: { asset_universe: "AAPL" }, call_id: "call-1", tool_name: "run_backtest" };
      expect(toolProgressText(progress, t)).toContain("AAPL");
      expect(toolProgressText(progress, t)).toBe(copy.chat.tools.progress.backtest.replace("{{asset_universe}}", "AAPL"));
      expect(toolProgressText(null, t)).toBe(copy.chat.status.working);
      expect(toolProgressText({ ...progress, locale_key: "future_unknown" }, t)).toBe(copy.chat.status.working);
      for (const old of ["interpret", "clarify", "confirm", "execute", "explain", "next_step", "extracting_strategy", "running_backtest", "calculating_metrics", "discovery_search"]) {
        expect(Object.keys(copy.chat.status)).not.toContain(old);
      }
    });
  }

  test("graph stage names never select a localized status", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf8");
    expect(chat).toContain("toolProgressText(event.data.tool_progress ?? null, t)");
    expect(chat).not.toContain("chat.status.${event.data.stage}");
  });
});
