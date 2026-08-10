import { describe, expect, test } from "bun:test";
import { readFileSync } from "fs";
import { join } from "path";

/* In-place edits on the confirmation card (§3.4): capital, dates, and costs
 * as three ExecutionDetails pills with one behaviour, the short bottom sheet
 * below the tablet threshold, and a typed no-turn endpoint that updates the
 * same card. The frontend renders backend capability truth and never invents
 * card state. */

const root = join(__dirname, "..");
const source = (path: string) => readFileSync(join(root, path), "utf-8");

describe("confirmation direct edit surface", () => {
  test("the card gates the controls on the backend capability and active state", () => {
    const card = source("components/chat/StrategyConfirmationCard.tsx");
    expect(card).toContain("capabilities?.direct_edits");
    expect(card).toContain("canShowActions");
    expect(card).toContain("ConfirmationDirectEditControls");
    // Costs joined the one in-place path; no separate turn-spending editor.
    expect(card).not.toContain("ExecutionCostEditor");
    expect(card).not.toContain("executionCostEditMessage");
  });

  test("one editing line hosts all three editors; actions share the card margin", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).toContain('"capital"');
    expect(editor).toContain('"dates"');
    expect(editor).toContain('"costs"');
    expect(editor).toContain('className="contents"');
    const card = source("components/chat/StrategyConfirmationCard.tsx");
    // The action pills align to the card's left content margin, on the same
    // px-4/sm:px-5 rhythm as every other section, not their own axis.
    expect(card).toContain(
      '"flex flex-wrap gap-2 border-t border-[#c9c9cd]/30 px-4 py-3.5 dark:border-white/[0.06] sm:px-5"',
    );
    expect(card).not.toContain("justify-center border-t");
  });

  test("the editors speak the ExecutionDetails idiom, not a second disclosure vocabulary", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).toContain('from "./ExecutionDetails"');
    expect(editor).toContain("<ExecutionDetails");
    // The old bespoke drawer is gone.
    expect(editor).not.toContain("grid-rows-[0fr]");
    expect(editor).not.toContain("ChevronUp");
    expect(editor).not.toContain("direct_edit.hide");

    const shared = source("components/chat/ExecutionDetails.tsx");
    // One component, two shapes: the read-only details list and the editable
    // panel share the pill trigger and panel classes.
    expect(shared).toContain("triggerPillClassName");
    expect(shared).toContain("panelClassName");
    expect(shared).toContain("<details");
    expect(shared).toContain("order-last basis-full");
    expect(shared).toContain("aria-expanded");

    const result = source("components/chat/StrategyResultCard.tsx");
    expect(result).toContain('from "./ExecutionDetails"');
    expect(result).not.toContain("function ExecutionDetails");

    // Confirm/cancel stay the round check/x controls; Enter and Escape work.
    expect(editor).toContain("<Check");
    expect(editor).toContain("<X");
    expect(editor).toContain('event.key === "Enter"');
    expect(editor).toContain('event.key === "Escape"');
  });

  test("the editors submit typed values through the no-turn endpoint, never prose", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).not.toContain("onAction");
    expect(editor).toContain("onDirectEdit(edit)");
    expect(editor).toContain("date_window");
    // Costs convert percent inputs to the endpoint's decimal rates.
    expect(editor).toContain("costEditDraftToRates");

    const handlers = source("components/chat/confirmation-superseding.ts");
    expect(handlers).toContain("directEditConfirmation(");
    // In place means in place: the edited message replaces itself; nothing
    // is appended and nothing else is marked superseded.
    expect(handlers).toContain("message.id === replacement.id");
    expect(handlers).not.toContain("appendSupersedingConfirmation(updated)");
    const chat = source("components/chat/ChatInterface.tsx");
    expect(chat).toContain("confirmationSupersedingHandlers(");

    const api = source("lib/argus-api.ts");
    expect(api).toContain("/direct-edit");
  });

  test("mobile reuses the short sheet primitive; wide screens get the inline panel", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).toContain('height="short"');
    expect(editor).toContain("BottomSheet");
    expect(editor).toContain("isBelowTablet");
  });

  test("input seeds come from typed fields, never parsed display strings", () => {
    const editor = source("components/chat/ConfirmationDirectEdit.tsx");
    expect(editor).toContain("display_facts?.capital");
    expect(editor).toContain("date_range?.start");
    expect(editor).toContain("costEditDraftFromDisplayFacts");
    expect(editor).not.toContain("rows.find");
  });

  test("unapplied edit changes disclose above the card in both locales", () => {
    const message = source("components/chat/ChatMessage.tsx");
    expect(message).toContain("confirmationEditDisclosureText");
    expect(message).toContain("confirmation-edit-disclosure");

    const lib = source("lib/confirmation-edit-disclosure.ts");
    expect(lib).toContain("edit_disclosure.targets");

    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));
    for (const bundle of [en, es]) {
      const disclosure = bundle.chat.confirmation.edit_disclosure;
      expect(disclosure.unapplied).toContain("{{targets}}");
      for (const target of [
        "asset",
        "benchmark",
        "capital",
        "date_window",
        "fees",
        "slippage",
        "generic",
      ]) {
        expect(typeof disclosure.targets[target]).toBe("string");
        expect(disclosure.targets[target]).not.toContain("—");
      }
    }
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
        "edit_costs",
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
      const costEditor = bundle.chat.confirmation.cost_editor;
      for (const key of ["fee_label", "slippage_label", "invalid"]) {
        expect(typeof costEditor[key]).toBe("string");
        expect(costEditor[key]).not.toContain("—");
      }
    }
    expect(es.chat.confirmation.direct_edit.edit_dates).toBe("Editar fechas");
    expect(es.chat.confirmation.direct_edit.edit_costs).toBe("Editar costos");
  });
});
