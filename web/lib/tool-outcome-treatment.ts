import {
  quietNoticeBodyClass,
  quietNoticeContainerClass,
  quietNoticeIconClass,
  retryableNoticeBodyClass,
  retryableNoticeContainerClass,
  retryableNoticeIconClass,
  retryableNoticeRetryPillClass,
} from "./failure-treatment";
import type { ToolOutcome, ToolRepair, ToolTranslator } from "./tool-result-card";
import type { DecisionRerunReasonCode } from "./decision-contract";

/**
 * The one owner mapping tool outcomes and decision re-run reasons onto the
 * shared failure treatments. The tool card, the answer dossier, the decision
 * view and the rail all read this and never pick a tone of their own.
 *
 * - `unavailable`: a model or provider outage; the retryable notice.
 * - `invalid`, `ambiguous`, `bounded`: the inputs cannot answer; the quiet
 *   notice naming the field, with the typed repair when the backend computed one.
 */
export type ToolOutcomeTone = "retryable" | "quiet";

export type ToolOutcomeTreatment = {
  tone: ToolOutcomeTone;
  code: string;
  fields: string[];
  message: string;
  repair: ToolRepair | null;
  classes: { container: string; icon: string; body: string; retryPill: string | null };
};

const NO_KEY = "";

function firstTranslation(t: ToolTranslator, keys: string[], values: Record<string, unknown>): string {
  for (const key of keys) {
    const rendered = t(key, { ...values, defaultValue: NO_KEY });
    if (rendered && rendered !== key) return rendered;
  }
  return "";
}

const QUIET_CLASSES = {
  container: quietNoticeContainerClass,
  icon: quietNoticeIconClass,
  body: quietNoticeBodyClass,
  retryPill: null,
};
const RETRYABLE_CLASSES = {
  container: retryableNoticeContainerClass,
  icon: retryableNoticeIconClass,
  body: retryableNoticeBodyClass,
  retryPill: retryableNoticeRetryPillClass,
};

export function toolOutcomeTreatment(
  outcome: ToolOutcome,
  t: ToolTranslator,
  fieldLabel: (name: string) => string = (name) => name,
): ToolOutcomeTreatment | null {
  if (outcome.status === "succeeded" || !outcome.failure) return null;
  const { code, fields } = outcome.failure;
  const field = fields.length > 0 ? fieldLabel(fields[0]) : "";
  const tone: ToolOutcomeTone = outcome.status === "unavailable" ? "retryable" : "quiet";
  const message = firstTranslation(t, [`tools.card.failure.${code}`, `tools.card.status.${outcome.status}`], { field }) ||
    t("tools.card.unavailable", { defaultValue: "This result is unavailable." });
  return {
    tone,
    code,
    fields,
    message,
    repair: outcome.failure.repair ?? null,
    classes: tone === "retryable" ? RETRYABLE_CLASSES : QUIET_CLASSES,
  };
}

/** A decision that cannot re-run keeps the existing reason codes; quiet, never alarming. */
export function decisionRerunTreatment(
  reasonCode: DecisionRerunReasonCode,
  t: ToolTranslator,
): ToolOutcomeTreatment {
  return {
    tone: "quiet",
    code: reasonCode,
    fields: [],
    message: firstTranslation(t, [`tools.decision.reason.${reasonCode}`], {}) ||
      t("tools.card.unavailable", { defaultValue: "This result is unavailable." }),
    repair: null,
    classes: QUIET_CLASSES,
  };
}

/** Recompute that changes nothing: the same copy the retest already uses. */
export function alreadyUpToDateText(t: ToolTranslator): string {
  return t("command_palette.retest_already_current", { defaultValue: "Already up to date" });
}
