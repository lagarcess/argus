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
  const copy = {
    es: {
      home: { title: "Cada cuenta. En su sitio. | Cuadrao", description: "Estamos construyendo Cuadrao para ayudarte a entender el dinero de tu negocio, planear pagos y mantener tus clientes y documentos en orden." },
      demo: { title: "Hablemos de tu negocio | Cuadrao", description: "Cuéntale a Lucas cómo llevas tu negocio y conoce lo que estamos preparando en Cuadrao." },
      personal: { title: "Tus finanzas, en orden. | Cuadrao Personal", description: "Conoce Cuadrao Personal y deja tu correo para recibir noticias sobre el acceso anticipado." },
    },
    en: {
      home: { title: "Every record. In its place. | Cuadrao", description: "We are building Cuadrao to help you understand your business money, plan payments and keep your customers and documents organized." },
      demo: { title: "Let's talk about your business | Cuadrao", description: "Tell Lucas how you run your business and explore what we are preparing at Cuadrao." },
      personal: { title: "Your finances, in order. | Cuadrao Personal", description: "Meet Cuadrao Personal and leave your email to hear about early access." },
    },
  }[locale][page];
  const image = {
    url: `https://cuadrao.ai/cuadrao-site/share-${page === "personal" ? "personal" : "business"}-${locale}.png`,
    width: 1200,
    height: 630,
    alt: page === "personal"
      ? locale === "es" ? "Cuadrao Personal. Tus finanzas, en orden." : "Cuadrao Personal. Your finances, in order."
      : locale === "es" ? "Cuadrao para negocios. Cada cuenta. En su sitio." : "Cuadrao Business. Every record. In its place.",
  };
  return {
    title: { absolute: copy.title },
    description: copy.description,
    openGraph: {
      type: "website",
      siteName: "Cuadrao",
      locale: locale === "es" ? "es_DO" : "en_US",
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
    robots: { index: false, follow: false },
    applicationName: "Cuadrao",
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
