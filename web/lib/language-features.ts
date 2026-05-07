export type ArgusLanguage = "en" | "es-419";

export type ArgusLanguageOption = {
  code: ArgusLanguage;
  name: string;
  translation: string;
};

export const ALL_LANGUAGES: ArgusLanguageOption[] = [
  { code: "en", name: "English", translation: "English" },
  { code: "es-419", name: "Español", translation: "Spanish" },
];

export const SPANISH_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_SPANISH === "true";

export const ENABLED_LANGUAGES = ALL_LANGUAGES.filter(
  (language) => language.code === "en" || SPANISH_ENABLED,
);

export const ENABLED_LANGUAGE_CODES = ENABLED_LANGUAGES.map(
  (language) => language.code,
);

export function normalizeEnabledLanguage(language?: string | null): ArgusLanguage {
  if (SPANISH_ENABLED && language?.toLowerCase().startsWith("es")) {
    return "es-419";
  }
  return "en";
}
