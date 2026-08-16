import type { TFunction } from "i18next";

/**
 * How a contribution period reads inside the one phrase that carries it,
 * "$200 monthly". No surface labels a period on its own, so there is no
 * standalone noun for it in any language.
 */
const PERIOD_FALLBACKS = {
  daily: "daily",
  weekly: "weekly",
  biweekly: "every two weeks",
  monthly: "monthly",
  quarterly: "quarterly",
} as const;

type ContributionPeriodKey = keyof typeof PERIOD_FALLBACKS;

export const CONTRIBUTION_PERIOD_KEYS = Object.keys(
  PERIOD_FALLBACKS,
) as ContributionPeriodKey[];

function canonicalPeriodKey(
  value: string | null | undefined,
): ContributionPeriodKey | null {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return null;
  return normalized in PERIOD_FALLBACKS
    ? (normalized as ContributionPeriodKey)
    : null;
}

export function contributionPeriodDisplayLabel(
  value: string | null | undefined,
  t?: TFunction,
) {
  const key = canonicalPeriodKey(value);
  if (!key) return value?.trim() || undefined;
  const fallback = PERIOD_FALLBACKS[key];
  return t
    ? t(`chat.confirmation.contribution_periods.${key}`, {
        defaultValue: fallback,
      })
    : fallback;
}

export function contributionPhrase(
  amount: string,
  period: string | null | undefined,
  t?: TFunction,
) {
  const label = contributionPeriodDisplayLabel(period, t);
  return label ? `${amount} ${label}` : amount;
}
