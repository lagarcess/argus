import { createInstance, type i18n } from "i18next";
import en from "../../public/locales/en/common.json";
import es from "../../public/locales/es-419/common.json";

export type TestLanguage = "en" | "es-419";

/** One i18next instance per language, loaded from the shipped locale files. */
export async function translate(language: TestLanguage): Promise<i18n> {
  const instance = createInstance();
  await instance.init({
    lng: language,
    fallbackLng: false,
    resources: { en: { translation: en }, "es-419": { translation: es } },
    interpolation: { escapeValue: false },
  });
  return instance;
}
