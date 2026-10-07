export const SITE_ORIGIN = "https://cuadrao.ai";

export const LOCALES = ["es", "en"] as const;
export const PAGES = ["home", "personal", "contact", "privacy"] as const;

export type BusinessLocale = (typeof LOCALES)[number];
export type BusinessPage = (typeof PAGES)[number];

// Spanish is the unprefixed default; English lives under /en. The slug is the
// only per-locale difference, so every URL, canonical, alternate and sitemap
// entry derives from this one table.
const SLUGS: Record<BusinessLocale, Record<BusinessPage, string>> = {
  es: { home: "", personal: "personal", contact: "contacto", privacy: "privacidad" },
  en: { home: "", personal: "personal", contact: "contact", privacy: "privacy" },
};

const HTML_LANG: Record<BusinessLocale, string> = { es: "es-DO", en: "en" };

export type SiteRoute = {
  locale: BusinessLocale;
  page: BusinessPage;
  path: string;
  url: string;
};

export function isLocale(value: string): value is BusinessLocale {
  return (LOCALES as readonly string[]).includes(value);
}

export function htmlLang(locale: BusinessLocale): string {
  return HTML_LANG[locale];
}

export function businessPath(
  locale: BusinessLocale,
  page: BusinessPage = "home",
): string {
  const prefix = locale === "en" ? "/en" : "";
  const slug = SLUGS[locale][page];
  return `${prefix}${slug ? `/${slug}` : ""}` || "/";
}

export const SITE_ROUTES: readonly SiteRoute[] = LOCALES.flatMap((locale) =>
  PAGES.map((page) => {
    const path = businessPath(locale, page);
    return { locale, page, path, url: `${SITE_ORIGIN}${path}` };
  }),
);

// The App Router tree is /[locale]/[[...slug]]. Spanish is served at the
// unprefixed public path by a rewrite, so the internal /es tree is never public.
export function internalPath(locale: BusinessLocale, page: BusinessPage): string {
  const slug = SLUGS[locale][page];
  return `/${locale}${slug ? `/${slug}` : ""}`;
}

export function pageFromSlug(
  locale: BusinessLocale,
  slug: readonly string[] | undefined,
): BusinessPage | null {
  const joined = (slug ?? []).join("/");
  return PAGES.find((page) => SLUGS[locale][page] === joined) ?? null;
}

export function slugSegments(locale: BusinessLocale, page: BusinessPage): string[] {
  const slug = SLUGS[locale][page];
  return slug ? [slug] : [];
}

export function alternateLanguages(page: BusinessPage): Record<string, string> {
  const urls = Object.fromEntries(
    LOCALES.map((locale) => [locale, `${SITE_ORIGIN}${businessPath(locale, page)}`]),
  );
  return { ...urls, "x-default": urls.es };
}

type Redirect = { source: string; destination: string; permanent: true };

// Marketing lived under /business while it shared the legacy web package.
const LEGACY_PAGE: Record<string, { locale: BusinessLocale; page: BusinessPage }> = {
  "/business": { locale: "es", page: "home" },
  "/business/personal": { locale: "es", page: "personal" },
  "/business/demo": { locale: "es", page: "contact" },
  "/business/en": { locale: "en", page: "home" },
  "/business/en/personal": { locale: "en", page: "personal" },
  "/business/en/demo": { locale: "en", page: "contact" },
};

export function nextRedirects(): Redirect[] {
  const legacy = Object.entries(LEGACY_PAGE).map(([source, { locale, page }]) => ({
    source,
    destination: businessPath(locale, page),
    permanent: true as const,
  }));
  const internalSpanish = PAGES.map((page) => ({
    source: internalPath("es", page),
    destination: businessPath("es", page),
    permanent: true as const,
  }));
  return [...legacy, ...internalSpanish];
}

export function nextRewrites(): { source: string; destination: string }[] {
  return PAGES.map((page) => ({
    source: businessPath("es", page),
    destination: internalPath("es", page),
  }));
}
