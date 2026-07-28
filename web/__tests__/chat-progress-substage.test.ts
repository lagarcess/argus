import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createInstance } from "i18next";

import { parseChatStreamFrame } from "@/lib/argus-api";

const root = join(import.meta.dir, "..");
const en = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
);
const es = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
);

async function appLikeT(resources: Record<string, unknown>) {
  const instance = createInstance();
  await instance.init({
    lng: "cimode-off",
    fallbackLng: false,
    resources: { "cimode-off": { translation: resources } },
    interpolation: { escapeValue: false },
    // Mirrors web/lib/i18n.ts: missing keys resolve falsy so || fallbacks fire.
    parseMissingKeyHandler: () => "",
  });
  return instance.t.bind(instance);
}

describe("sub-stage progress events", () => {
  test("parser carries detail on stage_start and drops empty detail", () => {
    expect(
      parseChatStreamFrame(
        'data: {"type":"stage_start","stage":"discovery_search","detail":"cybersecurity stocks"}',
      ),
    ).toEqual({
      event: "stage_start",
      data: { stage: "discovery_search", detail: "cybersecurity stocks" },
    });
    expect(
      parseChatStreamFrame(
        'data: {"type":"stage_start","stage":"discovery_verify"}',
      ),
    ).toEqual({ event: "stage_start", data: { stage: "discovery_verify" } });
    expect(
      parseChatStreamFrame(
        'data: {"type":"stage_start","stage":"discovery_search","detail":""}',
      ),
    ).toEqual({ event: "stage_start", data: { stage: "discovery_search" } });
  });

  test("both locales carry the discovery status keys with interpolation", () => {
    for (const locale of [en, es]) {
      const status = locale.chat.status;
      expect(status.discovery_search).toBeTruthy();
      expect(status.discovery_search_detail).toContain("{{detail}}");
      expect(status.discovery_verify).toBeTruthy();
    }
  });

  test("status label cascade: detail, detail-less, then neutral fallback", async () => {
    const t = await appLikeT(en);
    const label = (stage: string, detail?: string) =>
      (detail
        ? t(`chat.status.${stage}_detail`, { detail }) ||
          t(`chat.status.${stage}`)
        : t(`chat.status.${stage}`)) || t("chat.status.preparing");

    expect(label("discovery_search", "cybersecurity stocks")).toBe(
      "Searching the web — cybersecurity stocks",
    );
    expect(label("discovery_search")).toBe("Searching the web...");
    expect(label("discovery_verify")).toBe(
      "Verifying candidates against supported markets...",
    );
    // Unknown stage from a newer backend: neutral label, never the raw key.
    expect(label("future_unknown_stage")).toBe("Preparing results");
    expect(label("future_unknown_stage", "with detail")).toBe(
      "Preparing results",
    );
  });

  test("app i18n config resolves missing keys falsy", () => {
    const i18nSource = readFileSync(join(root, "lib/i18n.ts"), "utf-8");
    expect(i18nSource).toContain("parseMissingKeyHandler: () => ''");
  });

  test("ChatInterface passes detail through the label cascade", () => {
    const chat = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    expect(chat).toContain("t(`${stageKey}_detail`, { detail })");
    expect(chat).toContain('t("chat.status.preparing")');
  });
});
