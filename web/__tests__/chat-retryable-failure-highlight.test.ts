import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createInstance, type i18n } from "i18next";
import { I18nextProvider } from "react-i18next";

import ChatMessage from "../components/chat/ChatMessage";
import type { ChatActionOption, Message } from "../components/chat/types";

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

const amberTreatment = [
  "border-amber-700/25",
  "bg-amber-500/[0.06]",
  "dark:border-amber-300/20",
  "dark:bg-amber-300/[0.06]",
];

function renderMessage(
  message: Message,
  language: "en" | "es-419" = "en",
): string {
  return renderToStaticMarkup(
    React.createElement(
      I18nextProvider,
      { i18n: i18nByLanguage[language] },
      React.createElement(ChatMessage, { message }),
    ),
  );
}

function retryLastTurn(
  requestMessageId: string,
  message: string,
): ChatActionOption {
  return {
    id: `retry-last-turn-${requestMessageId}`,
    label: "Retry",
    labelKey: "common.retry",
    value: "Retry",
    type: "retry_last_turn",
    payload: {
      request_message_id: requestMessageId,
      message,
    },
  };
}

function hydratedFailure({
  code,
  content,
}: {
  code: string;
  content: string;
}): Message {
  const requestId = `request-${code}`;
  return {
    id: `assistant-${code}`,
    role: "ai",
    kind: "text",
    content,
    recoveryDisplay: { kind: "recovery_code", code },
    assistantRecoveryCode: code,
    actions: [retryLastTurn(requestId, content)],
  };
}

function expectAmberRetry(markup: string, localizedLabel: string): void {
  for (const className of amberTreatment) {
    expect(markup).toContain(className);
  }
  expect(markup).toContain('role="status"');
  expect(markup).toContain("lucide-message-square-warning");
  expect(markup).not.toContain('data-testid="user-turn-recovery"');
  expect(markup).not.toContain('data-testid="user-turn-retry"');
  expect(markup).toContain(`>${localizedLabel}</button>`);
}

describe("retryable failure highlight consistency (issue #313)", () => {
  test("hydrated Argus failures stay assistant-side and amber for every producer", () => {
    const producers = [
      hydratedFailure({
        code: "latest_result_followup_unavailable",
        content: "What was the worst drawdown?",
      }),
      hydratedFailure({
        code: "runtime_failure",
        content: "Compare that result with SPY.",
      }),
      hydratedFailure({
        code: "discovery_search_failed",
        content: "Find current cybersecurity stocks.",
      }),
      hydratedFailure({
        code: "runtime_failure",
        content: "Retest with current data",
      }),
    ];

    for (const message of producers) {
      expectAmberRetry(renderMessage(message, "en"), "Retry");
      expectAmberRetry(renderMessage(message, "es-419"), "Reintentar");
    }
  });

  test("live and hydrated retryable failures share the amber visual treatment", () => {
    const retry = retryLastTurn("request-live", "What was the worst drawdown?");
    const live = renderMessage({
      id: "assistant-live",
      role: "ai",
      kind: "text",
      content: "I could not safely answer that follow-up.",
      recoveryDisplay: {
        kind: "recovery_code",
        code: "latest_result_followup_unavailable",
      },
      assistantRecoveryCode: "latest_result_followup_unavailable",
      actions: [retry],
    });
    const hydrated = renderMessage(hydratedFailure({
      code: "latest_result_followup_unavailable",
      content: "I could not safely answer that follow-up.",
    }));

    for (const className of amberTreatment) {
      expect(live).toContain(className);
      expect(hydrated).toContain(className);
    }
    expect(live).toContain("lucide-message-square-warning");
    expect(hydrated).toContain("lucide-message-square-warning");
    expect(live).toContain(">Retry</button>");
    expect(hydrated).toContain(">Retry</button>");
  });

  test("non-retryable recovery, clarification, and capability answers stay unstyled", () => {
    const nonRetryable = renderMessage({
      id: "request-non-retryable",
      role: "user",
      kind: "text",
      content: "Test an unsupported setup",
      recoveryDisplay: {
        kind: "recovery_code",
        code: "artifact_action_retry_non_retryable",
      },
    });
    const clarification = renderMessage({
      id: "assistant-clarification",
      role: "ai",
      kind: "text",
      content: "Which date range should I use?",
    });
    const capability = renderMessage({
      id: "assistant-capability",
      role: "ai",
      kind: "text",
      content: "I can test one asset class at a time.",
    });

    expect(nonRetryable).toContain('data-testid="user-turn-recovery"');
    expect(nonRetryable).not.toContain('data-testid="user-turn-retry"');
    for (const markup of [nonRetryable, clarification, capability]) {
      for (const className of amberTreatment) {
        expect(markup).not.toContain(className);
      }
      expect(markup).not.toContain("lucide-message-square-warning");
    }
  });

  test("an unaccepted user-side retry keeps the existing muted treatment", () => {
    const inputFailure = renderMessage({
      id: "request-not-accepted",
      role: "user",
      kind: "text",
      content: "Test AAPL",
      recoveryDisplay: {
        kind: "recovery_code",
        code: "turn_abandoned",
      },
      actions: [retryLastTurn("request-not-accepted", "Test AAPL")],
    });

    expect(inputFailure).toContain('data-testid="user-turn-recovery"');
    expect(inputFailure).toContain('data-testid="user-turn-retry"');
    expect(inputFailure).toContain("lucide-rotate-ccw");
    expect(inputFailure).not.toContain("lucide-message-square-warning");
    for (const className of amberTreatment) {
      expect(inputFailure).not.toContain(className);
    }
  });
});
