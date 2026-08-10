import { describe, expect, test } from "bun:test";
import { readFileSync } from "fs";
import { join } from "path";

/* Direct capital/date edits (§3.4): a dedicated row in the shape of the
 * edit-costs row, an inline drawer on wide screens, the short bottom sheet
 * below the tablet threshold, and a typed no-turn endpoint. The frontend
 * renders backend capability truth and never invents card state. */

const root = join(__dirname, "..");
const source = (path: string) => readFileSync(join(root, path), "utf-8");

describe("confirmation direct edit surface", () => {
  test("the card gates the row on the backend capability and active state", () => {
    const card = source("components/chat/StrategyConfirmationCard.tsx");
    expect(card).toContain("capabilities?.direct_edits");
    expect(card).toContain("canShowActions");
    expect(card).toContain("ConfirmationDirectEditRow");
  });

  test("the editor submits typed values through the no-turn endpoint, never prose", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    // The cost editor composes a chat message; the direct editor must not.
    expect(editor).not.toContain("onAction");
    expect(editor).toContain("onDirectEdit(edit)");
    expect(editor).toContain("date_window");

    const chat = source("components/chat/ChatInterface.tsx");
    expect(chat).toContain("directEditConfirmation(");
    expect(chat).toContain("appendSupersedingConfirmation(created)");

    const api = source("lib/argus-api.ts");
    expect(api).toContain("/direct-edit");
  });

  test("mobile reuses the short sheet primitive; wide screens get the inline drawer", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).toContain('height="short"');
    expect(editor).toContain("BottomSheet");
    expect(editor).toContain("isBelowTablet");
    expect(editor).toContain("aria-expanded");
    expect(editor).toContain("aria-controls");
    expect(editor).toContain("grid-rows-[1fr]");
    expect(editor).toContain("motion-reduce:transition-none");
  });

  test("input seeds come from typed fields, never parsed display strings", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).toContain("display_facts?.capital");
    expect(editor).toContain("date_range?.start");
    expect(editor).not.toContain("rows.find");
  });

  test("both locales carry the editor strings, without em dashes", () => {
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));
    for (const bundle of [en, es]) {
      const directEdit = bundle.chat.confirmation.direct_edit;
      for (const key of [
        "edit_capital",
        "edit_contribution",
        "edit_dates",
        "capital_label",
        "contribution_label",
        "start_label",
        "end_label",
        "apply",
        "cancel",
        "close",
        "invalid_capital",
        "invalid_dates",
        "failed",
      ]) {
        expect(typeof directEdit[key]).toBe("string");
        expect(directEdit[key].length).toBeGreaterThan(0);
        expect(directEdit[key]).not.toContain("—");
      }
    }
    expect(es.chat.confirmation.direct_edit.edit_dates).toBe("Editar fechas");
  });
});
