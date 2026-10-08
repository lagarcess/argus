import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { tFromCatalog } from "./support/catalog-translator";
import {
  offersPersonalChat,
  recoveryDisplayFromRecoveryState,
  recoveryDisplayText,
} from "../lib/chat-recovery-display";

const root = join(import.meta.dir, "..");
const enCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf8"),
) as Record<string, unknown>;
const esCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
) as Record<string, unknown>;

describe("business chat tool refusal", () => {
  const refusal = (params?: Record<string, string>) =>
    recoveryDisplayFromRecoveryState({
      code: "business_chat_tool_unavailable",
      retryable: false,
      ...(params ? { params } : {}),
    });

  test("renders the founder's sentence in both languages", () => {
    const display = refusal();
    expect(display).not.toBeNull();
    expect(recoveryDisplayText(display!, tFromCatalog(esCatalog))).toBe(
      "Esta función no está disponible en el chat de tu negocio.",
    );
    expect(recoveryDisplayText(display!, tFromCatalog(enCatalog))).toBe(
      "This feature isn't available in your business chat.",
    );
  });

  test("links to Personal chat only when the backend says it runs that function", () => {
    expect(offersPersonalChat(refusal({ personal_chat: "available" }))).toBe(true);
    expect(offersPersonalChat(refusal())).toBe(false);
    expect(
      offersPersonalChat(
        recoveryDisplayFromRecoveryState({
          code: "research_lookup_unavailable",
          retryable: false,
          params: { personal_chat: "available" },
        }),
      ),
    ).toBe(false);
  });

  test("the old pointer to Personal chat is gone from every catalog", () => {
    for (const catalog of [enCatalog, esCatalog]) {
      const text = JSON.stringify(catalog);
      expect(text).not.toContain("from your personal chat");
      expect(text).not.toContain("desde tu chat personal");
    }
  });
});
