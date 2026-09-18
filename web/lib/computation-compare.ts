import type { ComputationDifference } from "./computation-contract";
import { toolFactValue, type ToolTranslator } from "./tool-result-card";

const MINUS = "−";

/** One side of a compared fact, in the fact's own unit. The number is the backend's. */
export function comparedValueText(difference: ComputationDifference, side: "left" | "right", t: ToolTranslator, locale: string): string {
  return toolFactValue({ name: difference.name, label: difference.label, value: difference[side], unit: difference.unit }, t, locale);
}

/** The backend's difference, signed, in the fact's own unit. */
export function differenceText(difference: ComputationDifference, t: ToolTranslator, locale: string): string {
  const magnitude = toolFactValue(
    { name: difference.name, label: difference.label, value: Math.abs(difference.difference), unit: difference.unit },
    t,
    locale,
  );
  if (difference.difference > 0) return `+${magnitude}`;
  if (difference.difference < 0) return `${MINUS}${magnitude}`;
  return magnitude;
}

/** A card whose inputs cite a public page can have those inputs looked up again. */
export function hasCitedInputs(card: { arguments: Record<string, unknown> }): boolean {
  const sources = card.arguments.sources;
  if (!sources || typeof sources !== "object" || Array.isArray(sources)) return false;
  return Object.values(sources as Record<string, unknown>).some(
    (source) => Boolean(source) && typeof source === "object" && (source as Record<string, unknown>).kind === "page",
  );
}
