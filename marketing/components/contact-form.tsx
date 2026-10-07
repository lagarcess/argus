"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { ArrowRight, Check } from "lucide-react";
import { businessPath } from "@/lib/site-routes";
import { businessContent, type BusinessLocale } from "./content";
import { newSubmissionId } from "./submission-id";
import styles from "./business.module.css";

type Field = "name" | "email" | "description";
type FormValues = Record<Field, string>;
type SendState =
  | { status: "idle" }
  | { status: "sending" }
  | { status: "sent"; values: FormValues }
  | { status: "error"; kind: "unavailable" | "rateLimited" | "rejected" };

const EMPTY_VALUES: FormValues = { name: "", email: "", description: "" };
const subscribeToHydration = (): (() => void) => () => {};
const clientSnapshot = (): boolean => true;
const serverSnapshot = (): boolean => false;
const REQUIRED_FIELDS = ["name", "email"] as const;
const REQUEST_TIMEOUT_MS = 15_000;

export function ContactForm({ locale }: { locale: BusinessLocale }) {
  const copy = businessContent[locale].contact;
  const hydrated = useSyncExternalStore(
    subscribeToHydration,
    clientSnapshot,
    serverSnapshot,
  );
  const [values, setValues] = useState<FormValues>(EMPTY_VALUES);
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [state, setState] = useState<SendState>({ status: "idle" });
  const form = useRef<HTMLFormElement>(null);
  const confirmation = useRef<HTMLHeadingElement>(null);
  const pending = useRef(false);
  // A retry of the same text reuses its id so the server can recognise it. Any
  // edit is a different message and gets a new id.
  const attempt = useRef<{ id: string; signature: string } | null>(null);

  useEffect(() => {
    if (state.status === "sent") confirmation.current?.focus();
  }, [state.status]);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (pending.current) return;
    const nextErrors: Partial<Record<Field, string>> = {};
    for (const field of REQUIRED_FIELDS) {
      if (!values[field].trim()) nextErrors[field] = copy.required;
    }
    const emailInput = form.current?.elements.namedItem(
      "email",
    ) as HTMLInputElement | null;
    if (values.email.trim() && emailInput?.validity.typeMismatch)
      nextErrors.email = copy.invalidEmail;
    setErrors(nextErrors);
    const first = REQUIRED_FIELDS.find((field) => nextErrors[field]);
    if (first) {
      (
        form.current?.elements.namedItem(first) as HTMLInputElement | null
      )?.focus();
      return;
    }

    const signature = JSON.stringify(values);
    if (attempt.current?.signature !== signature) {
      attempt.current = { id: newSubmissionId(), signature };
    }
    const website =
      (form.current?.elements.namedItem("website") as HTMLInputElement | null)
        ?.value ?? "";
    pending.current = true;
    setState({ status: "sending" });
    try {
      const response = await fetch("/api/inquiries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...values,
          locale,
          submissionId: attempt.current.id,
          website,
        }),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      if (response.status === 202) {
        attempt.current = null;
        setState({ status: "sent", values });
      } else {
        setState({
          status: "error",
          kind:
            response.status === 429
              ? "rateLimited"
              : response.status === 400
                ? "rejected"
                : "unavailable",
        });
      }
    } catch {
      setState({ status: "error", kind: "unavailable" });
    } finally {
      pending.current = false;
    }
  }

  const sending = state.status === "sending";
  const failure = state.status === "error" ? copy[state.kind] : null;

  return (
    <div className={styles.formArea}>
      {state.status === "sent" ? (
        <section className={styles.review} aria-labelledby="contact-sent-title">
          <span className={styles.sentMark}>
            <Check size={22} aria-hidden="true" />
          </span>
          <h2 id="contact-sent-title" ref={confirmation} tabIndex={-1}>
            {copy.successTitle}
          </h2>
          <p>{copy.successBody}</p>
          <dl>
            {([...REQUIRED_FIELDS, "description"] as const).map((field) => (
              <div key={field}>
                <dt>{copy[field]}</dt>
                <dd>{state.values[field].trim() || copy.empty}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : (
        <form
          ref={form}
          onSubmit={submit}
          noValidate
          aria-busy={sending}
          aria-describedby="contact-privacy"
          className={styles.demoForm}
        >
          <noscript>
            <p className={styles.localNotice}>{copy.noScript}</p>
          </noscript>
          <fieldset className={styles.formFields} disabled={!hydrated}>
            {REQUIRED_FIELDS.map((field) => (
              <div className={styles.field} key={field}>
                <label htmlFor={`contact-${field}`}>{copy[field]}</label>
                <input
                  id={`contact-${field}`}
                  name={field}
                  type={field === "email" ? "email" : "text"}
                  autoComplete={field}
                  maxLength={field === "email" ? 254 : 120}
                  required
                  placeholder={copy[`${field}Placeholder`]}
                  value={values[field]}
                  aria-invalid={!!errors[field]}
                  aria-describedby={
                    errors[field] ? `contact-${field}-error` : undefined
                  }
                  readOnly={sending}
                  onChange={(event) => {
                    setValues({ ...values, [field]: event.target.value });
                    if (errors[field])
                      setErrors({ ...errors, [field]: undefined });
                  }}
                />
                {errors[field] && (
                  <p id={`contact-${field}-error`} className={styles.fieldError}>
                    {errors[field]}
                  </p>
                )}
              </div>
            ))}
            <div className={styles.field}>
              <label htmlFor="contact-description">
                {copy.description} <span>{copy.optional}</span>
              </label>
              <textarea
                id="contact-description"
                name="description"
                rows={4}
                maxLength={1000}
                placeholder={copy.descriptionPlaceholder}
                value={values.description}
                readOnly={sending}
                onChange={(event) =>
                  setValues({ ...values, description: event.target.value })
                }
              />
            </div>
            <div className={styles.srOnly} aria-hidden="true">
              <label htmlFor="contact-website">Website</label>
              <input
                id="contact-website"
                name="website"
                type="text"
                tabIndex={-1}
                autoComplete="off"
                defaultValue=""
              />
            </div>
            {Object.keys(errors).some((field) => errors[field as Field]) && (
              <p className={styles.srOnly} role="alert">
                {copy.errors}
              </p>
            )}
            {failure && (
              <p id="contact-failure" className={styles.formFailure} role="alert">
                {failure}
              </p>
            )}
            <button
              type="submit"
              disabled={!hydrated || sending}
              className={styles.button}
            >
              {sending ? copy.sending : copy.submit}
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </fieldset>
        </form>
      )}
      <p id="contact-privacy" className={styles.formPrivacy}>
        {copy.privacy}{" "}
        <a href={businessPath(locale, "privacy")}>{copy.privacyLink}</a>
      </p>
    </div>
  );
}
