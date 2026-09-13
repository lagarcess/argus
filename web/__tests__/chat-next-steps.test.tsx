import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { TFunction } from "i18next";
import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import NextMoveRow from "../components/chat/NextMoveRow";
import NextStepsSection from "../components/chat/NextStepsSection";
import type { ChatActionOption } from "../components/chat/types";
import { nextExperimentRowsFromMetadata } from "../lib/chat-next-experiments";
import {
  messageNextSteps,
  nextStepsFromMetadata,
  type NextStep,
} from "../lib/chat-next-steps";

const root = join(import.meta.dir, "..");
const locales = {
  en: JSON.parse(readFileSync(join(root, "public/locales/en/common.json"), "utf-8")),
  "es-419": JSON.parse(
    readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
  ),
};
type Language = keyof typeof locales;

const QUESTIONS: Record<Language, string> = {
  en: "What drove DOCN's drop between February and August 2025?",
  "es-419": "¿Qué impulsó la caída de DOCN entre febrero y agosto de 2025?",
};

function translator(language: Language): TFunction {
  const lookup = (key: string): unknown =>
    key
      .split(".")
      .reduce<unknown>(
        (node, part) =>
          node && typeof node === "object"
            ? (node as Record<string, unknown>)[part]
            : undefined,
        locales[language],
      );
  return ((key: string, fallback?: unknown) => {
    const value = lookup(key);
    if (typeof value === "string") return value;
    if (typeof fallback === "string") return fallback;
    const defaultValue = (fallback as { defaultValue?: unknown } | undefined)
      ?.defaultValue;
    return typeof defaultValue === "string" ? defaultValue : key;
  }) as unknown as TFunction;
}

function metadata(language: Language): Record<string, unknown> {
  return {
    next_experiments: {
      version: "argus_next_experiments/v1",
      source_run_id: "run-docn",
      rows: [
        {
          kind: "change_date_range",
          label: "Test a different date range",
          label_key: "chat.next_experiments.labels.change_date_range",
        },
        {
          kind: "supported_ma_crossover",
          label: "Try a moving average crossover",
          label_key: "chat.next_experiments.labels.supported_ma_crossover",
        },
      ],
    },
    next_steps: {
      version: "argus_next_steps/v1",
      items: [
        { type: "test", kind: "supported_ma_crossover" },
        { type: "question", text: QUESTIONS[language] },
        { type: "test", kind: "change_date_range" },
        { type: "test", kind: "not_offered" },
        { type: "question", text: QUESTIONS[language] },
      ],
    },
  };
}

function stepsFor(language: Language): NextStep[] {
  const source = metadata(language);
  const steps = nextStepsFromMetadata(source, nextExperimentRowsFromMetadata(source));
  expect(steps).not.toBeNull();
  return steps ?? [];
}

function rowElements(node: ReactNode): ReactElement<{ onClick: () => void; ariaLabel?: string }>[] {
  if (Array.isArray(node)) return node.flatMap(rowElements);
  if (!isValidElement(node)) return [];
  const element = node as ReactElement<{ children?: ReactNode; onClick: () => void }>;
  if (element.type === NextMoveRow) return [element];
  return rowElements(element.props.children);
}

describe("one list of next steps under an answer", () => {
  test("keeps the backend's order, resolves tests to typed rows and drops repeats", () => {
    const steps = stepsFor("en");

    expect(
      steps.map((step) => (step.type === "test" ? step.row.kind : step.text)),
    ).toEqual(["supported_ma_crossover", QUESTIONS.en, "change_date_range"]);
  });

  test("a runnable step sends its typed action and a question sends its text", () => {
    const actions: ChatActionOption[] = [];
    const t = translator("en");
    const section = NextStepsSection({
      steps: stepsFor("en"),
      disabled: false,
      isBelowTablet: false,
      locale: "en",
      onAction: (action) => actions.push(action),
      sourceRunId: "run-docn",
      t,
    });

    for (const row of rowElements(section)) row.props.onClick();

    expect(actions).toEqual([
      {
        label: "Try a moving average crossover",
        labelKey: "chat.next_experiments.labels.supported_ma_crossover",
        value: "Try a moving average crossover",
      },
      { label: QUESTIONS.en, value: QUESTIONS.en },
      {
        label: "Test a different date range",
        labelKey: "chat.next_experiments.labels.change_date_range",
        value: "Test a different date range",
        type: "refine_strategy",
        presentation: "result",
        payload: { run_id: "run-docn", next_experiment_kind: "change_date_range" },
      },
    ]);
  });

  const renderCases: { language: Language; heading: string; tests: [string, string] }[] = [
    {
      language: "en",
      heading: "Try next",
      tests: ["Try a moving average crossover", "Test a different date range"],
    },
    {
      language: "es-419",
      heading: "Qué probar después",
      tests: ["Probar un cruce de medias móviles", "Probar otro rango de fechas"],
    },
  ];
  for (const { language, heading, tests } of renderCases) {
    test(`renders one section in plain words in ${language}`, () => {
      const html = renderToStaticMarkup(
        <NextStepsSection
          steps={stepsFor(language)}
          disabled={false}
          isBelowTablet={false}
          locale={language}
          sourceRunId="run-docn"
          t={translator(language)}
        />,
      );

      expect(html.match(/<section/g)?.length).toBe(1);
      expect(html).toContain(heading);
      const labels = [...html.matchAll(/aria-label="([^"]+)"/g)].map((match) =>
        match[1].replaceAll("&#x27;", "'"),
      );
      expect(labels).toEqual([heading, tests[0], QUESTIONS[language], tests[1]]);
      expect(html).not.toMatch(/supported|compatible|SMA\/EMA/i);
    });
  }

  test("a message without the list offers its Try next rows alone", () => {
    const source = metadata("en");
    const rows = nextExperimentRowsFromMetadata(source) ?? [];

    expect(messageNextSteps({ nextExperiments: rows })).toEqual(
      rows.map((row) => ({ type: "test", row })),
    );
    expect(messageNextSteps({ nextSteps: stepsFor("en"), nextExperiments: rows })).toEqual(
      stepsFor("en"),
    );
    expect(
      nextStepsFromMetadata({ next_steps: { version: "argus_next_steps/v0", items: [] } }, rows),
    ).toBeNull();
  });

  test("the locales carry no separate questions section and no system words in row labels", () => {
    for (const locale of Object.values(locales)) {
      expect(locale.chat.suggested_questions).toBeUndefined();
      const labels = [
        ...Object.values(locale.chat.next_experiments.labels),
        ...Object.values(locale.chat.next_experiments.labels_short),
      ].join(" ");
      expect(labels).not.toMatch(/supported|compatible|SMA\/EMA/i);
    }
  });
});
