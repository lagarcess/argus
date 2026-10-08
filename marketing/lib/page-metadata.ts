import type { BusinessLocale, BusinessPage } from "./site-routes";

type PageMetadata = { title: string; description: string };

export const PAGE_METADATA: Record<BusinessLocale, Record<BusinessPage, PageMetadata>> = {
  es: {
    home: {
      title: "Cada cuenta. En su sitio. | Cuadrao",
      description:
        "Estamos construyendo Cuadrao para ayudarte a entender el dinero de tu negocio, planear pagos y mantener tus clientes y documentos en orden.",
    },
    contact: {
      title: "Hablemos de tu negocio | Cuadrao",
      description:
        "Cuéntale a Lucas cómo llevas tu negocio y conoce lo que estamos preparando en Cuadrao.",
    },
    personal: {
      title: "Tus finanzas, en orden. | Cuadrao Personal",
      description:
        "Conoce Cuadrao Personal y deja tu correo para recibir noticias sobre el acceso anticipado.",
    },
    privacy: {
      title: "Privacidad | Cuadrao",
      description:
        "Qué datos recibe Cuadrao cuando escribes o te registras, para qué los usamos y cómo pedir que los eliminemos.",
    },
  },
  en: {
    home: {
      title: "Every record. In its place. | Cuadrao",
      description:
        "We are building Cuadrao to help you understand your business money, plan payments and keep your customers and documents organized.",
    },
    contact: {
      title: "Let's talk about your business | Cuadrao",
      description:
        "Tell Lucas how you run your business and explore what we are preparing at Cuadrao.",
    },
    personal: {
      title: "Your finances, in order. | Cuadrao Personal",
      description:
        "Meet Cuadrao Personal and leave your email to hear about early access.",
    },
    privacy: {
      title: "Privacy | Cuadrao",
      description:
        "What data Cuadrao receives when you write to us or sign up, what we use it for and how to ask us to delete it.",
    },
  },
};

type ShareImage = { url: string; width: number; height: number; alt: string };

export function shareImage(locale: BusinessLocale, page: BusinessPage): ShareImage {
  const personal = page === "personal";
  return {
    url: `/cuadrao-site/share-${personal ? "personal" : "business"}-${locale}.png`,
    width: 1200,
    height: 630,
    alt: personal
      ? locale === "es" ? "Cuadrao Personal. Tus finanzas, en orden." : "Cuadrao Personal. Your finances, in order."
      : locale === "es" ? "Cuadrao para negocios. Cada cuenta. En su sitio." : "Cuadrao Business. Every record. In its place.",
  };
}
