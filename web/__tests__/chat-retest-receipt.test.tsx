import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createInstance, type i18n } from "i18next";
import { I18nextProvider } from "react-i18next";

import ChatMessage from "../components/chat/ChatMessage";
import type { Message } from "../components/chat/types";
import {
  retestActionOption,
  type RetestReceipt,
} from "../lib/chat-retest";

const root = join(import.meta.dir, "..");
const catalogs = {
  en: JSON.parse(
    readFileSync(join(root, "public/locales/en/common.json"), "utf8"),
  ) as Record<string, unknown>,
  "es-419": JSON.parse(
    readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
  ) as Record<string, unknown>,
};

async function localizedI18n(language: "en" | "es-419"): Promise<i18n> {
  const instance = createInstance();
  await instance.init({
    lng: language,
    fallbackLng: "en",
    ns: ["common"],
    defaultNS: "common",
    interpolation: { escapeValue: false },
    resources: {
      en: { common: catalogs.en },
      "es-419": { common: catalogs["es-419"] },
    },
  });
  return instance;
}

const i18nByLanguage = {
  en: await localizedI18n("en"),
  "es-419": await localizedI18n("es-419"),
};

const READY_RECEIPT: RetestReceipt = {
  sourceRunId: "run-42",
  symbols: ["GLD"],
  strategyFamily: "buy_and_hold",
  durationDays: 911,
  duration: { unit: "year", count: 2.5, approximate: true },
  cadence: null,
  timeframe: "1D",
  period: {
    originalDateRange: { start: "2024-01-01", end: "2024-12-31" },
    requestedDateRange: { start: "2024-01-01", end: "2026-07-31" },
    effectiveDateRange: { start: "2024-01-01", end: "2026-06-30" },
    durationDays: 911,
    duration: { unit: "year", count: 2.5, approximate: true },
  },
};

const MULTI_SYMBOL_RECEIPT: RetestReceipt = {
  ...READY_RECEIPT,
  symbols: ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"],
};

type PendingRetestMessage = Message & { retestReceiptPending?: boolean };

function retestMessage(
  overrides: Partial<PendingRetestMessage> = {},
): PendingRetestMessage {
  return {
    id: "user-retest-1",
    role: "user",
    kind: "action",
    content: "Retest with current data",
    selectedAction: retestActionOption("run-42"),
    ...overrides,
  };
}

function renderMessage(
  message: PendingRetestMessage,
  language: "en" | "es-419" = "en",
): string {
  return renderToStaticMarkup(
    React.createElement(
      I18nextProvider,
      { i18n: i18nByLanguage[language] },
      React.createElement(ChatMessage, { message: message as Message }),
    ),
  );
}

describe("Retest receipt visual continuity", () => {
  test("optimistic and ready turns render the same receipt shell", () => {
    const pending = renderMessage(retestMessage({ retestReceiptPending: true }));
    const ready = renderMessage(retestMessage({ retestReceipt: READY_RECEIPT }));

    expect(pending).toContain('data-retest-receipt-state="pending"');
    expect(ready).toContain('data-retest-receipt-state="ready"');
    expect(pending).toContain('data-retest-receipt-context-row="true"');
    expect(ready).toContain('data-retest-receipt-context-row="true"');
    expect(pending).not.toContain("GLD · Buy and hold");
    expect(ready).toContain(
      "GLD · Buy and hold · Jan 1, 2024 – Dec 31, 2024 → Jan 1, 2024 – Jun 30, 2026 · about 2.5 years",
    );
  });

  test("the pending shell localizes only the trusted action label", () => {
    const pending = renderMessage(
      retestMessage({
        content: "Volver a probar con datos actuales",
        retestReceiptPending: true,
      }),
      "es-419",
    );

    expect(pending).toContain("Volver a probar con datos actuales");
    expect(pending).toContain('data-retest-receipt-state="pending"');
    expect(pending).not.toContain("GLD");
  });

  test("pending and five-symbol ready receipts reserve the supported wrapped height", () => {
    const pending = renderMessage(retestMessage({ retestReceiptPending: true }));
    const ready = renderMessage(
      retestMessage({ retestReceipt: MULTI_SYMBOL_RECEIPT }),
    );

    for (const markup of [pending, ready]) {
      expect(markup).toContain("min-h-[95px]");
      expect(markup).toContain("sm:min-h-[57px]");
      expect(markup).toContain('data-retest-receipt-context-row="true"');
    }
    expect(ready).toContain("EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD");
  });
});
