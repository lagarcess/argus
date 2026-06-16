import type { TFunction } from "i18next";

const CADENCE_FALLBACKS = {
  daily: "Daily",
  weekly: "Weekly",
  biweekly: "Biweekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
} as const;

type CadenceKey = keyof typeof CADENCE_FALLBACKS;

function canonicalCadenceKey(value: string | null | undefined): CadenceKey | null {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return null;
  return normalized in CADENCE_FALLBACKS ? (normalized as CadenceKey) : null;
}

export function cadenceDisplayLabel(
  value: string | null | undefined,
  t?: TFunction,
) {
  const key = canonicalCadenceKey(value);
  if (!key) return value?.trim() || undefined;
  const fallback = CADENCE_FALLBACKS[key];
  return t ? t(`chat.cadence.${key}`, { defaultValue: fallback }) : fallback;
}
