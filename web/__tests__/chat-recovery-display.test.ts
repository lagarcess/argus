import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  recoveryDisplayFromMetadata,
  recoveryDisplayText,
} from "../lib/chat-recovery-display";

const root = join(import.meta.dir, "..");
const enCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf8"),
) as Record<string, unknown>;
const esCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
) as Record<string, unknown>;

function tFromCatalog(catalog: Record<string, unknown>) {
  return (key: string, options?: Record<string, unknown> | string) => {
    const template = key
      .split(".")
      .reduce<unknown>(
        (value, segment) =>
          typeof value === "object" && value !== null && !Array.isArray(value)
            ? (value as Record<string, unknown>)[segment]
            : undefined,
        catalog,
      );
    if (typeof template !== "string") {
      return key;
    }
    const values =
      typeof options === "object" && options !== null
        ? options
        : ({} as Record<string, unknown>);
    return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
      String(values[name] ?? ""),
    );
  };
}

function flattenedKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }
  return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) =>
    flattenedKeys(nested, prefix ? `${prefix}.${key}` : key),
  );
}

describe("chat recovery display", () => {
  test("renders recovery codes through locale catalogs", () => {
    const display = recoveryDisplayFromMetadata({
      recovery: {
        code: "runtime_failure",
        retryable: true,
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "Something went wrong. Your conversation is saved. Please try again.",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "Algo salió mal. Tu conversación está guardada. Intenta de nuevo.",
    );
  });

  test("does not replace live clarification prompts with generic recovery text", () => {
    const display = recoveryDisplayFromMetadata({
      response_intent: {
        kind: "clarification",
        semantic_needs: ["period"],
        facts: {
          strategy: {
            asset_universe: ["AAPL"],
          },
        },
      },
    });

    expect(display).toBeNull();
  });

  test("renders unsupported recovery options from typed replacement values", () => {
    const display = recoveryDisplayFromMetadata({
      response_intent: {
        kind: "unsupported_recovery",
        facts: {
          strategy: {
            asset_universe: ["NVDA"],
          },
          unsupported_constraints: [
            {
              raw_value: "invalid_chronological_date_range",
            },
          ],
        },
        options: [
          {
            replacement_values: {
              simplify_logic: "rsi_only",
            },
          },
          {
            replacement_values: {
              strategy_type: "buy_and_hold",
            },
          },
        ],
      },
    });

    const text = recoveryDisplayText(display, tFromCatalog(esCatalog));

    expect(text).toBe(
      "Esa regla no define por sí sola cuándo comprar o vender para NVDA. ¿Qué camino quieres usar: Usar una regla RSI compatible o Comparar con comprar y mantener?",
    );
    expect(text).not.toContain("invalid_chronological_date_range");
  });

  test("recovery locale keys stay in parity", () => {
    for (const namespace of [
      "chat.recovery",
      "chat.clarification",
      "chat.simplification_options",
    ]) {
      const enKeys = flattenedKeys(
        namespace
          .split(".")
          .reduce<unknown>(
            (value, segment) =>
              typeof value === "object" &&
              value !== null &&
              !Array.isArray(value)
                ? (value as Record<string, unknown>)[segment]
                : undefined,
            enCatalog,
          ),
      );
      const esKeys = flattenedKeys(
        namespace
          .split(".")
          .reduce<unknown>(
            (value, segment) =>
              typeof value === "object" &&
              value !== null &&
              !Array.isArray(value)
                ? (value as Record<string, unknown>)[segment]
                : undefined,
            esCatalog,
          ),
      );

      expect(esKeys).toEqual(enKeys);
    }
  });
});
