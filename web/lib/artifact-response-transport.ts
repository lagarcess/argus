import type { TFunction } from "i18next";
import { recoveryDisplayFromMetadata, recoveryDisplayText } from "./chat-recovery-display";

/** Localize successful typed replies before the chat's nonempty-message seam. */
export function localizeArtifactFinalPayload<T extends { assistant_response?: string | null }>(
  payload: T,
  t: TFunction,
  locale: string,
): T {
  const display = recoveryDisplayFromMetadata(payload);
  if (display?.kind !== "artifact_assumptions" && display?.kind !== "result_breakdown") return payload;
  return { ...payload, assistant_response: recoveryDisplayText(display, t, locale) };
}
