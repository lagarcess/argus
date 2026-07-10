export const strategiesEnabled =
  process.env.NEXT_PUBLIC_STRATEGIES_ENABLED === "true";

export const collectionsEnabled =
  process.env.NEXT_PUBLIC_COLLECTIONS_ENABLED === "true";

export const omnisearchEnabled =
  process.env.NEXT_PUBLIC_OMNISEARCH_ENABLED !== "false";

export const privateAlphaOnboardingEnabled =
  process.env.NEXT_PUBLIC_PRIVATE_ALPHA_ONBOARDING_ENABLED === "true";

export const chatExploratorySuggestionsEnabled =
  process.env.NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED === "true";
