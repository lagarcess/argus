export const strategiesEnabled =
  process.env.NEXT_PUBLIC_STRATEGIES_ENABLED === "true";

export const collectionsEnabled =
  process.env.NEXT_PUBLIC_COLLECTIONS_ENABLED === "true";

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
