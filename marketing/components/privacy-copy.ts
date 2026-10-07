import { businessContactEmail } from "./site-copy";
import type { BusinessLocale } from "@/lib/site-routes";

type Section = { title: string; paragraphs?: string[]; items?: string[] };

type PrivacyCopy = {
  eyebrow: string;
  title: string;
  intro: string;
  updated: string;
  sections: Section[];
};

const email = businessContactEmail;

const es: PrivacyCopy = {
  eyebrow: "PRIVACIDAD",
  title: "Qué datos recibimos y para qué.",
  intro:
    "Cuadrao es un proyecto en preparación de Lucas Garcés. Este sitio recibe datos solo cuando escribes por el formulario de contacto o dejas tu correo para el acceso anticipado.",
  updated: "Actualizado el 7 de octubre de 2026",
  sections: [
    {
      title: "Si nos escribes",
      paragraphs: [
        "Recibimos tu nombre, tu correo, el comentario opcional y el idioma de la página. Los usamos solo para responderte.",
        "El mensaje llega por correo electrónico al buzón de Cuadrao. No lo guardamos en otra base de datos y no lo usamos para enviarte publicidad.",
      ],
    },
    {
      title: "Si pides acceso anticipado a Cuadrao Personal",
      paragraphs: [
        "Recibimos tu correo, el idioma de la página, la fecha del registro y la versión de este texto que aceptaste. Los usamos solo para avisarte cuando haya acceso disponible. Registrarte no crea una cuenta ni garantiza acceso inmediato.",
      ],
    },
    {
      title: "Qué no recopilamos",
      paragraphs: [
        "Este sitio no usa cookies, herramientas de analítica ni seguimiento publicitario, y no guarda datos en tu navegador. Las tipografías se sirven desde el mismo sitio.",
        "Te pedimos que no escribas documentos, números de cuenta ni información financiera privada en el formulario.",
      ],
    },
    {
      title: "Quién procesa los datos",
      items: [
        "Render aloja el sitio y puede registrar datos técnicos de la conexión, como la dirección IP.",
        "Resend envía el correo con tu mensaje al buzón de Cuadrao.",
        "Supabase guarda los registros de acceso anticipado en servidores de Estados Unidos (Ohio).",
        "Cloudflare administra el dominio cuadrao.ai.",
      ],
    },
    {
      title: "Cuánto tiempo los conservamos",
      paragraphs: [
        "Tu mensaje permanece en el buzón de Cuadrao mientras haga falta para responderte y dar seguimiento a la conversación.",
        "Tu registro de acceso anticipado permanece hasta que pidas retirarlo. Al retirarlo borramos tu correo y conservamos solo una huella técnica de la dirección, sin la dirección misma, para no volver a registrarte ni escribirte.",
      ],
    },
    {
      title: "Tus opciones",
      paragraphs: [
        `Puedes pedirnos ver, corregir o eliminar tus datos, o retirar tu registro, escribiendo a ${email}. Atendemos esas solicitudes manualmente.`,
      ],
    },
  ],
};

const en: PrivacyCopy = {
  eyebrow: "PRIVACY",
  title: "What data we receive and why.",
  intro:
    "Cuadrao is a project in preparation by Lucas Garcés. This site receives data only when you write through the contact form or leave your email for early access.",
  updated: "Updated October 7, 2026",
  sections: [
    {
      title: "If you write to us",
      paragraphs: [
        "We receive your name, your email, the optional comment and the page language. We use them only to reply to you.",
        "The message arrives by email in Cuadrao's mailbox. We do not store it in another database and we do not use it to send you advertising.",
      ],
    },
    {
      title: "If you request Cuadrao Personal early access",
      paragraphs: [
        "We receive your email, the page language, the signup date and the version of this text you accepted. We use them only to tell you when access is available. Signing up does not create an account or guarantee immediate access.",
      ],
    },
    {
      title: "What we do not collect",
      paragraphs: [
        "This site does not use cookies, analytics tools or advertising tracking, and it does not store data in your browser. Fonts are served from the site itself.",
        "Please do not enter documents, account numbers or private financial information in the form.",
      ],
    },
    {
      title: "Who processes the data",
      items: [
        "Render hosts the site and may log technical connection data, such as the IP address.",
        "Resend sends the email with your message to Cuadrao's mailbox.",
        "Supabase stores early-access signups on servers in the United States (Ohio).",
        "Cloudflare manages the cuadrao.ai domain.",
      ],
    },
    {
      title: "How long we keep it",
      paragraphs: [
        "Your message stays in Cuadrao's mailbox for as long as it is needed to reply and follow up.",
        "Your early-access signup stays until you ask to remove it. When you remove it we delete your email and keep only a technical fingerprint of the address, not the address itself, so we do not register or email you again.",
      ],
    },
    {
      title: "Your choices",
      paragraphs: [
        `You can ask us to show, correct or delete your data, or to remove your signup, by writing to ${email}. We handle these requests by hand.`,
      ],
    },
  ],
};

export const privacyCopy: Record<BusinessLocale, PrivacyCopy> = { es, en };
