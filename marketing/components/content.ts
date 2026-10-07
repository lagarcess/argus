import { siteCopy } from "./site-copy";
export type { BusinessLocale } from "@/lib/site-routes";

const es = {
  navigation: {
    business: "Para negocios",
    personal: "Personal",
    approach: "La idea",
    about: "Nosotros",
    demo: siteCopy.es.cta,
    menu: "Abrir menú",
    close: "Cerrar menú",
    label: "Navegación principal",
    language: "Idioma",
    back: "Volver a negocios",
    skip: "Ir al contenido",
  },
  closing: { footerLabel: "Navegación al pie" },
  demo: {
    noScript:
      "Activa JavaScript para probar este formulario local. No se enviará ningún dato.",
    notice:
      "Vista local. Este formulario no envía datos ni agenda una reunión.",
    name: "Tu nombre",
    email: "Correo electrónico",
    description: "¿Qué te cuesta mantener al día?",
    optional: "(opcional)",
    namePlaceholder: "Tu nombre",
    emailPlaceholder: "tu@negocio.com",
    descriptionPlaceholder: "Unas palabras son suficientes.",
    submit: "Revisar mi mensaje",
    required: "Completa este campo.",
    invalidEmail: "Escribe un correo válido, como tu@negocio.com.",
    reviewTitle: "Tu mensaje, listo para revisar.",
    reviewBody:
      "No se ha enviado nada ni se ha reservado una reunión. El contacto aún no está conectado en esta vista local.",
    edit: "Editar mensaje",
    empty: "Sin comentario",
    privacy:
      "Los datos permanecen en esta página. No se envían ni se guardan en un servidor.",
    errors: "Revisa los campos marcados.",
  },
  personal: {
    eyebrow: "CUADRAO PERSONAL",
    title: "Tu dinero también merece estar cuadrao.",
    body: "Estamos preparando Cuadrao para tus finanzas personales. Pronto compartiremos más.",
    status: "En preparación",
    return: "Conoce Cuadrao para negocios",
  },
};
const en: typeof es = {
  navigation: {
    business: "Business",
    personal: "Personal",
    approach: "The idea",
    about: "About",
    demo: siteCopy.en.cta,
    menu: "Open menu",
    close: "Close menu",
    label: "Main navigation",
    language: "Language",
    back: "Back to Business",
    skip: "Skip to content",
  },
  closing: { footerLabel: "Footer navigation" },
  demo: {
    noScript: "Enable JavaScript to try this local form. No data will be sent.",
    notice: "Local preview. This form does not send data or book a meeting.",
    name: "Your name",
    email: "Email address",
    description: "What’s hard to keep up with?",
    optional: "(optional)",
    namePlaceholder: "Your name",
    emailPlaceholder: "you@business.com",
    descriptionPlaceholder: "A few words are enough.",
    submit: "Review my message",
    required: "Complete this field.",
    invalidEmail: "Enter a valid email, such as you@business.com.",
    reviewTitle: "Your message is ready to review.",
    reviewBody:
      "Nothing has been sent and no meeting has been booked. Contact is not connected in this local preview yet.",
    edit: "Edit message",
    empty: "No comment",
    privacy:
      "Your details stay on this page. Nothing is sent or saved to a server.",
    errors: "Check the marked fields.",
  },
  personal: {
    eyebrow: "CUADRAO PERSONAL",
    title: "Your money deserves to be squared away, too.",
    body: "We’re preparing Cuadrao for your personal finances. More to come soon.",
    status: "In preparation",
    return: "Explore Cuadrao for business",
  },
};
export const businessContent = { es, en };
