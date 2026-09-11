import type { TFunction } from "i18next";
import type { Message } from "@/components/chat/types";
import { normalizeAssistantDisplayText } from "./chat-display-text";
import { confirmationCardCopyText, resultCardCopyText } from "./chat-card-copy-text";
import { confirmationCardViewModel } from "./confirmation-card-view-model";
import { resultCardViewModel } from "./result-card-view-model";
import { resultMessageReadoutText } from "./result-readout-display";
import { recoveryDisplayCopyText } from "./chat-recovery-display";
import { pendingArtifactCardFromPayload } from "./pending-artifact-card";
import { toolCardCopyText } from "./tool-result-card";

/** Copy consumes the same localized frame/card view as the transcript. */
export function chatMessageCopyText(message: Message, t: TFunction, locale: string): string {
  if (message.role !== "user" && message.kind === "strategy_result" && message.result) {
    return resultCardCopyText(resultCardViewModel(message.result, { t, locale }), t);
  }
  const readout = resultMessageReadoutText(message, t, locale);
  if (readout !== null) return readout;
  if (message.role !== "user") {
    const recovery = recoveryDisplayCopyText(message.recoveryDisplay, t, locale);
    if (recovery) return normalizeAssistantDisplayText(recovery);
  }
  const confirmation = pendingArtifactCardFromPayload(message.confirmation);
  if (message.kind === "strategy_confirmation" && confirmation?.kind === "backtest") {
    return normalizeAssistantDisplayText(confirmationCardCopyText(confirmationCardViewModel(confirmation, t, locale), t, locale));
  }
  const text = [message.content ?? "", ...(message.toolResultCards ?? []).map((card) => toolCardCopyText(card, t, locale))].filter(Boolean).join("\n\n");
  return message.role === "user" ? text : normalizeAssistantDisplayText(text);
}
