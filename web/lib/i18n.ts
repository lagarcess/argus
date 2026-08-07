import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpBackend from 'i18next-http-backend';
import { ENABLED_LANGUAGE_CODES } from './language-features';

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: ENABLED_LANGUAGE_CODES,
    defaultNS: 'common',
    ns: ['common'],
    interpolation: {
      escapeValue: false,
    },
    // Missing keys resolve to "" (falsy), so `t(dynamicKey) || t(fallback)`
    // actually falls back instead of rendering the raw key.
    parseMissingKeyHandler: () => '',
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      // Language comes from what the user actually set, not from geography.
      // navigator.language of es-MX or es-ES is still Spanish, so it resolves
      // to the one Spanish Argus ships.
      convertDetectedLanguage: (language: string) =>
        language.toLowerCase().startsWith('es') ? 'es-419' : language,
    },
  });

export default i18n;
