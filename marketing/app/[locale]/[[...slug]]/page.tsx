import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  BusinessLanding,
  ContactPage,
  PersonalPage,
  PrivacyPage,
} from "@/components/business-pages";
import { PAGE_METADATA, shareImage } from "@/lib/page-metadata";
import {
  LOCALES,
  PAGES,
  SITE_ORIGIN,
  alternateLanguages,
  businessPath,
  isLocale,
  pageFromSlug,
  slugSegments,
  type BusinessLocale,
  type BusinessPage,
} from "@/lib/site-routes";

type Props = { params: Promise<{ locale: string; slug?: string[] }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return LOCALES.flatMap((locale) =>
    PAGES.map((page) => ({ locale, slug: slugSegments(locale, page) })),
  );
}

async function resolveRoute(
  params: Props["params"],
): Promise<{ locale: BusinessLocale; page: BusinessPage }> {
  const { locale, slug } = await params;
  if (!isLocale(locale)) notFound();
  const page = pageFromSlug(locale, slug);
  if (!page) notFound();
  return { locale, page };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, page } = await resolveRoute(params);
  const copy = PAGE_METADATA[locale][page];
  const image = shareImage(locale, page);
  return {
    metadataBase: new URL(SITE_ORIGIN),
    title: { absolute: copy.title },
    description: copy.description,
    applicationName: "Cuadrao",
    alternates: {
      canonical: businessPath(locale, page),
      languages: alternateLanguages(page),
    },
    openGraph: {
      type: "website",
      siteName: "Cuadrao",
      locale: locale === "es" ? "es_DO" : "en_US",
      url: businessPath(locale, page),
      title: copy.title,
      description: copy.description,
      images: [image],
    },
    twitter: {
      card: "summary_large_image",
      title: copy.title,
      description: copy.description,
      images: [image.url],
    },
    manifest: null,
  };
}

export default async function SitePage({ params }: Props) {
  const { locale, page } = await resolveRoute(params);
  switch (page) {
    case "home":
      return <BusinessLanding locale={locale} />;
    case "contact":
      return <ContactPage locale={locale} />;
    case "personal":
      return <PersonalPage locale={locale} />;
    case "privacy":
      return <PrivacyPage locale={locale} />;
  }
}
