import type { TFunction } from "i18next";
import { resultReadoutContentFromMetadata } from "./result-readout-content";
import { resultBreakdownText, resultQuickTakeText } from "./result-readout-display";
import { resultReadoutFacts } from "./result-readout-facts";
import { recoveryDisplayFromMetadata, recoveryDisplayText } from "./chat-recovery-display";

/** Localize successful typed replies before the chat's nonempty-message seam. */
export function localizeArtifactFinalPayload<T extends { assistant_response?: string | null }>(
  payload: T,
  t: TFunction,
  locale: string,
): T {
  const metadata = payload as Record<string, unknown>;
  if (metadata.artifact_presentation_kind === "result") {
    return { ...payload, assistant_response: resultQuickTakeText(resultReadoutFacts(metadata.result_fact_bank), t, locale, resultReadoutContentFromMetadata(payload)) };
  }
  const display = recoveryDisplayFromMetadata(payload);
  if (display?.kind !== "artifact_assumptions" && display?.kind !== "result_breakdown") return payload;
  return { ...payload, assistant_response: display.kind === "result_breakdown"
    ? resultBreakdownText(display.facts, t, locale, resultReadoutContentFromMetadata(payload))
    : recoveryDisplayText(display, t, locale) };
}
