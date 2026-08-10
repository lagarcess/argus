import enCommon from "@/public/locales/en/common.json";
import esCommon from "@/public/locales/es-419/common.json";
import { SPANISH_ENABLED, type ArgusLanguage } from "./language-features";

/**
 * Server-side copy for the public receipt route.
 *
 * The receipt is a standalone public page opened by people who are not signed
 * in, so there is no stored language preference to honour and no client i18n
 * provider to wait for. Language comes from the request, the page renders in one
 * pass, and the strings still live in the shared locale files so they translate
 * with everything else.
 */
export type ReceiptCopy = typeof enCommon.receipt;

const COPY: Record<ArgusLanguage, ReceiptCopy> = {
  en: enCommon.receipt,
  "es-419": esCommon.receipt as ReceiptCopy,
};

export function receiptLanguageFromAcceptLanguage(
  header: string | null | undefined,
): ArgusLanguage {
  if (!SPANISH_ENABLED || !header) return "en";
  const preferred = header
    .split(",")
    .map((entry) => {
      const [tag, ...parameters] = entry.trim().split(";");
      const quality = parameters
        .map((parameter) => parameter.trim())
        .find((parameter) => parameter.startsWith("q="));
      const weight = quality ? Number.parseFloat(quality.slice(2)) : 1;
      return { tag: tag.trim().toLowerCase(), weight: Number.isNaN(weight) ? 0 : weight };
    })
    .filter((entry) => entry.tag && entry.weight > 0)
    .sort((left, right) => right.weight - left.weight);
  for (const entry of preferred) {
    if (entry.tag.startsWith("es")) return "es-419";
    if (entry.tag.startsWith("en")) return "en";
  }
  return "en";
}

export function receiptCopy(language: ArgusLanguage): ReceiptCopy {
  return COPY[language] ?? COPY.en;
}

export function formatReceiptDate(
  value: string | null | undefined,
  language: ArgusLanguage,
): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat(language === "es-419" ? "es-419" : "en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

export function interpolate(
  template: string,
  values: Record<string, string | number>,
): string {
  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}
