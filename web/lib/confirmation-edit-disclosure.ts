import type { TFunction } from "i18next";
import type { StrategyConfirmationEditDisclosure } from "@/components/chat/types";

/**
 * §3.2 disclosure: the part of an edit that could not be applied, rendered as
 * a lead-in above the card. Typed refusals always win: the planner writes
 * its note before the resolver rules on each operation, so prose can claim a
 * change the card does not carry. When typed unapplied entries exist, the
 * locale catalog names them in the user's language; the note is the voice
 * only for note-only refusals, where the planner itself declined in prose.
 */

const TARGET_LABEL_KEYS: Record<string, string> = {
  asset: "chat.confirmation.edit_disclosure.targets.asset",
  benchmark: "chat.confirmation.edit_disclosure.targets.benchmark",
  cadence: "chat.confirmation.edit_disclosure.targets.cadence",
  capital: "chat.confirmation.edit_disclosure.targets.capital",
  date_window: "chat.confirmation.edit_disclosure.targets.date_window",
  fees: "chat.confirmation.edit_disclosure.targets.fees",
  recurring_contribution:
    "chat.confirmation.edit_disclosure.targets.recurring_contribution",
  starting_capital: "chat.confirmation.edit_disclosure.targets.starting_capital",
  slippage: "chat.confirmation.edit_disclosure.targets.slippage",
  strategy_family: "chat.confirmation.edit_disclosure.targets.strategy_family",
  timeframe: "chat.confirmation.edit_disclosure.targets.timeframe",
};

export function confirmationEditDisclosureText(
  disclosure: StrategyConfirmationEditDisclosure | null | undefined,
  t: TFunction,
): string | null {
  if (!disclosure) {
    return null;
  }
  const targets = (disclosure.unapplied ?? [])
    .map((entry) => String(entry.target ?? "").trim())
    .filter(Boolean)
    .map((target) =>
      t(
        TARGET_LABEL_KEYS[target] ??
          "chat.confirmation.edit_disclosure.targets.generic",
        target.replace(/_/g, " "),
      ),
    );
  if (targets.length > 0) {
    const unique = Array.from(new Set(targets));
    return t("chat.confirmation.edit_disclosure.unapplied", {
      defaultValue: "I could not change {{targets}}; the rest is applied below.",
      targets: unique.join(", "),
    });
  }
  const note = String(disclosure.note ?? "").trim();
  return note || null;
}
