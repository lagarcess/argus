import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  BusinessLanding,
  DemoPage,
  PersonalPage,
} from "@/components/business/business-pages";
import {
  BUSINESS_SITE_ROOT,
  businessPreviewEnabled,
  resolveBusinessPathname,
} from "@/lib/business-site";

// Recheck the preview gate on each request, including a production-mode local build.
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ path?: string[] }> };

async function resolveRoute(params: Props["params"]) {
  if (!businessPreviewEnabled(process.env.CUADRAO_WEBSITE_PREVIEW)) notFound();
  const { path = [] } = await params;
  const route = resolveBusinessPathname(
    `${BUSINESS_SITE_ROOT}${path.length ? `/${path.join("/")}` : ""}`,
  );
  if (!route) notFound();
  return route;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, page } = await resolveRoute(params);
  const title = {
    es: {
      home: "Tu negocio, claro y cuadrao",
      demo: "Hablemos de tu negocio",
      personal: "Cuadrao para ti",
    },
    en: {
      home: "Your business, clear and squared away",
      demo: "Let's talk about your business",
      personal: "Cuadrao for you",
    },
  }[locale][page];
  return {
    title: `${title} | cuadrao`,
    description:
      locale === "es"
        ? "Estamos construyendo una forma más clara de llevar las finanzas de tu negocio. Conoce Cuadrao for business."
        : "We're building a clearer way to understand your business finances. Meet Cuadrao for business.",
    robots: { index: false, follow: false },
    applicationName: "cuadrao",
    manifest: null,
    icons: { icon: "/business/icon.svg", apple: [] },
  };
}

export default async function BusinessPage({ params }: Props) {
  const { locale, page } = await resolveRoute(params);
  return (
    <div lang={locale === "es" ? "es-DO" : "en"}>
      {page === "home" && <BusinessLanding locale={locale} />}
      {page === "demo" && <DemoPage locale={locale} />}
      {page === "personal" && <PersonalPage locale={locale} />}
    </div>
  );
}
