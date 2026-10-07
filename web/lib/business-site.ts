export type BusinessLocale = "es" | "en";
export type BusinessPage = "home" | "demo" | "personal";

export const BUSINESS_SITE_ROOT = "/business";

export function businessPath(
  locale: BusinessLocale,
  page: BusinessPage = "home",
) {
  const language = locale === "en" ? "/en" : "";
  const surface = page === "home" ? "" : `/${page}`;
  return `${BUSINESS_SITE_ROOT}${language}${surface}`;
}

export function resolveBusinessPathname(pathname: string | null) {
  for (const locale of ["es", "en"] as const) {
    for (const page of ["home", "demo", "personal"] as const) {
      if (pathname === businessPath(locale, page)) return { locale, page };
    }
  }
  return null;
}

export function businessPreviewEnabled(value: string | undefined) {
  return value === "true";
}
