"use client";

import Image from "next/image";
import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { ArrowRight, Check } from "lucide-react";
import { businessPath } from "@/lib/site-routes";
import type { BusinessLocale } from "./content";
import { businessContactEmail } from "./site-copy";
import styles from "./personal-early-access.module.css";

type SignupState = { status: "idle" } | { status: "submitting" } | { status: "success" } | { status: "error"; message: string; rejected: boolean };

const homePreview = { src: "/cuadrao-site/personal-home-preview.png", width: 1206, height: 2622 } as const;
const subscribeToHydration = (): (() => void) => () => {};
const clientSnapshot = (): boolean => true;
const serverSnapshot = (): boolean => false;

const copy = {
  es: {
    eyebrow: "CUADRAO PERSONAL · ACCESO ANTICIPADO",
    title: "Tus finanzas, en orden.",
    benefit: "Tus cuentas y el próximo pago, a la vista.",
    body: "Estamos preparando la app. Déjanos tu correo y te avisaremos cuando puedas probarla.",
    label: "Correo electrónico",
    button: "Avísame cuando pueda probarla",
    saving: "Guardando tu registro…",
    privacy: "Usaremos tu correo solo para avisarte sobre el acceso anticipado a Cuadrao. Para retirar tu registro, escríbenos a",
    privacyLink: "Política de privacidad",
    rateLimited: "Hiciste varios intentos seguidos. Espera unos minutos e inténtalo de nuevo.",
    success: "Ya estás en la lista.",
    saved: "Tu correo quedó registrado para el acceso anticipado.",
    next: "Cuando haya invitaciones disponibles, podremos contactarte. Registrarte no garantiza acceso inmediato.",
    error: `No pudimos guardar tu correo. Inténtalo de nuevo o escríbenos a ${businessContactEmail}.`,
    invalid: "Revisa tu correo e inténtalo de nuevo.",
    noScript: "Activa JavaScript para usar este formulario.",
    caption: "Vista previa · datos de ejemplo. El diseño puede cambiar.",
    nextPayment: "Tu próximo pago",
    alt: "Inicio de Cuadrao Personal con datos de ejemplo: saludo a Alex, balance disponible y próximo pago de Internet.",
  },
  en: {
    eyebrow: "CUADRAO PERSONAL · EARLY ACCESS",
    title: "Your finances, in order.",
    benefit: "Your accounts and next payment, at a glance.",
    body: "We’re preparing the app. Leave your email and we’ll let you know when you can try it.",
    label: "Email address",
    button: "Let me know when I can try it",
    saving: "Saving your signup…",
    privacy: "We'll use your email only to tell you about Cuadrao early access. To remove your signup, email",
    privacyLink: "Privacy policy",
    rateLimited: "You made several attempts in a row. Wait a few minutes and try again.",
    success: "You're on the list.",
    saved: "Your email is registered for early access.",
    next: "We can contact you when invitations become available. Signing up does not guarantee immediate access.",
    error: `We couldn't save your email. Try again or write to ${businessContactEmail}.`,
    invalid: "Check your email address and try again.",
    noScript: "Enable JavaScript to use this form.",
    caption: "Preview in Spanish · sample data. The design may change.",
    nextPayment: "Your next payment",
    alt: "Cuadrao Personal Home preview in Spanish with sample data: a greeting to Alex, available balance and an upcoming Internet payment.",
  },
} as const;

export function PersonalEarlyAccess({ locale }: { locale: BusinessLocale }) {
  const c = copy[locale];
  const hydrated = useSyncExternalStore(subscribeToHydration, clientSnapshot, serverSnapshot);
  const [email, setEmail] = useState("");
  const [state, setState] = useState<SignupState>({ status: "idle" });
  const confirmation = useRef<HTMLHeadingElement>(null);
  const pending = useRef(false);

  useEffect(() => {
    if (state.status === "success") confirmation.current?.focus();
  }, [state.status]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    pending.current = true;
    const website = (event.currentTarget.elements.namedItem("website") as HTMLInputElement | null)?.value ?? "";
    setState({ status: "submitting" });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("/api/signups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, locale, website }),
        signal: controller.signal,
      });
      const result: unknown = await response.json();
      if (response.ok && typeof result === "object" && result !== null && "status" in result && result.status === "registered") {
        setState({ status: "success" });
      } else {
        setState({
          status: "error",
          message: response.status === 400 ? c.invalid : response.status === 429 ? c.rateLimited : c.error,
          rejected: response.status === 400,
        });
      }
    } catch {
      setState({ status: "error", message: c.error, rejected: false });
    } finally {
      clearTimeout(timeout);
      pending.current = false;
    }
  }

  return (
    <section className={styles.hero} aria-labelledby="personal-title">
      <div className={styles.content}>
        <p className={styles.eyebrow}>{c.eyebrow}</p>
        <h1 id="personal-title">{c.title}</h1>
        <p className={styles.intro}>{c.benefit}</p>
      </div>
      <div className={styles.capture} id="early-access">
        <p className={styles.invitation}>{c.body}</p>
        <div className={styles.signup}>
          {state.status === "success" ? (
            <div className={styles.confirmation}>
              <span className={styles.check}><Check size={24} aria-hidden="true" /></span>
              <h2 ref={confirmation} tabIndex={-1}>{c.success}</h2>
              <p>{c.saved}</p>
              <p>{c.next}</p>
            </div>
          ) : (
            <form method="post" action="/api/signups" onSubmit={submit} aria-busy={state.status === "submitting"}>
              <noscript><p className={styles.local}>{c.noScript}</p></noscript>
              <fieldset className={styles.formFields} disabled={!hydrated}>
                <label htmlFor="personal-email">{c.label}</label>
                <input id="personal-email" type="email" name="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" inputMode="email" maxLength={254} required aria-describedby={state.status === "error" ? "signup-error signup-privacy" : "signup-privacy"} aria-invalid={(state.status === "error" && state.rejected) || undefined} readOnly={state.status === "submitting"} placeholder={locale === "es" ? "tu@correo.com" : "you@example.com"} />
                <div className={styles.trap} aria-hidden="true">
                  <label htmlFor="personal-website">Website</label>
                  <input id="personal-website" name="website" type="text" tabIndex={-1} autoComplete="off" defaultValue="" />
                </div>
                <button type="submit" disabled={!hydrated} aria-disabled={state.status === "submitting"}>
                  {state.status === "submitting" ? c.saving : c.button}
                  <ArrowRight size={19} aria-hidden="true" />
                </button>
                {state.status === "error" && <p id="signup-error" className={styles.error} role="alert">{state.message}</p>}
              </fieldset>
            </form>
          )}
        </div>
        <p className={styles.privacy} id="signup-privacy">{c.privacy} <a href={`mailto:${businessContactEmail}`}>{businessContactEmail}</a>. <a href={businessPath(locale, "privacy")}>{c.privacyLink}</a>.</p>
      </div>
      <figure className={styles.preview}>
        <div className={styles.previewBackdrop}>
          <div className={styles.phone}>
            <Image {...homePreview} alt={c.alt} sizes="(max-width: 700px) 230px, 300px" priority />
          </div>
          <div className={styles.paymentCloseup} aria-hidden="true">
            <span>{c.nextPayment}</span>
            <div className={styles.paymentCrop}>
              <Image {...homePreview} alt="" sizes="(max-width: 700px) 320px, 340px" />
            </div>
          </div>
        </div>
        <figcaption>{c.caption}</figcaption>
      </figure>
    </section>
  );
}
