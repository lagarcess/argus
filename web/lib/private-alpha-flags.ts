export const omnisearchEnabled =
  process.env.NEXT_PUBLIC_OMNISEARCH_ENABLED !== "false";

export const chatExploratorySuggestionsEnabled =
  process.env.NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED === "true";

export function guestAccessEnabledFromEnv(value: string | undefined): boolean {
  if (value === undefined || value.trim() === "") return true;
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  return false;
}

export const guestAccessEnabled = guestAccessEnabledFromEnv(
  process.env.NEXT_PUBLIC_GUEST_ACCESS_ENABLED,
);

// Default off, and it stays off when this lane lands. Turning sharing on is a
// separate founder decision from merging it.
export const evidenceReceiptSharingEnabled =
  process.env.NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED === "true";
