import type { StrategyConfirmationPayload } from "@/components/chat/types";

export type PendingArtifactCard = StrategyConfirmationPayload & {
  kind: "backtest";
};

/** One wire boundary for streamed, persisted and directly supplied cards. */
export function pendingArtifactCardFromPayload(value: unknown): PendingArtifactCard | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const card = value as Record<string, unknown>;
  if (!Array.isArray(card.rows)) return null;
  // Only the absence of a discriminator identifies a legacy backtest card.
  // An explicit future kind must never inherit backtest rendering or actions.
  if ("kind" in card && card.kind !== "backtest") return null;
  return { ...card, kind: "backtest" } as PendingArtifactCard;
}
