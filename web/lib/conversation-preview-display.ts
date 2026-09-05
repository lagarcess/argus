import type { TFunction } from "i18next";
import { strategyDisplayLabel } from "./strategy-display";

export type ConversationPreview = {
  kind: "text" | "result" | "confirmation" | "assumptions" | "breakdown" | "empty" | "unavailable";
  text?: string | null;
  symbols: string[];
  template?: string | null;
};

/** Artifact prose has one owner: the current reader's language bundle. */
export function conversationPreviewText(
  preview: ConversationPreview | null | undefined,
  t: TFunction,
): string {
  if (preview?.kind === "text") return preview.text ?? "";
  const label = t(`conversation_preview.${preview?.kind ?? "unavailable"}`);
  const symbols = preview?.symbols.join(", ");
  const strategy = strategyDisplayLabel(preview?.template, t);
  return [label, symbols, strategy].filter(Boolean).join(" · ");
}
