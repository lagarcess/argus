/**
 * Argus Feature Flag Management
 * Enforces NEXT_PUBLIC_<NAME> convention from AGENTS.md
 */

export const Features = {
  SOCIAL_AUTH: process.env.NEXT_PUBLIC_FEATURE_SOCIAL_AUTH !== "false", // Default ON
  STRATEGY_SIMULATION: process.env.NEXT_PUBLIC_FEATURE_STRATEGY_SIMULATION !== "false", // Default ON
  EXPERIMENTAL_THREE_JS: process.env.NEXT_PUBLIC_FEATURE_THREE_JS === "true",
} as const;

export type FeatureKey = keyof typeof Features;

export function isFeatureEnabled(key: FeatureKey): boolean {
  return Features[key];
}
