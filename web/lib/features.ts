/**
 * Argus feature flags keyed off a single environment variable.
 * Set NEXT_PUBLIC_APP_ENV to "development" or "production".
 */
import { APP_ENV } from "@/lib/app-env";

const featureProfiles = {
  development: {
    MULTI_RULES: true,
    SOCIAL_AUTH: true,
    STRATEGY_SIMULATION: true,
    EXPERIMENTAL_THREE_JS: true,
  },
  production: {
    MULTI_RULES: false,
    SOCIAL_AUTH: true,
    STRATEGY_SIMULATION: true,
    EXPERIMENTAL_THREE_JS: false,
  },
} as const;

export const Features = featureProfiles[APP_ENV];

export type FeatureKey = keyof typeof Features;

export function isFeatureEnabled(key: FeatureKey): boolean {
  return Features[key];
}
