"use client";

import { useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { ArrowRight, Info, Pencil } from "lucide-react";
import { businessContent, type BusinessLocale } from "./content";
import styles from "./business.module.css";

type Field = "name" | "email" | "description";
type FormValues = Record<Field, string>;
const EMPTY_VALUES: FormValues = {
  name: "",
  email: "",
  description: "",
};
const subscribeToHydration = (): (() => void) => () => {};
const clientSnapshot = (): boolean => true;
const serverSnapshot = (): boolean => false;
const REQUIRED_FIELDS = ["name", "email"] as const;

export function DemoForm({ locale }: { locale: BusinessLocale }) {
  const copy = businessContent[locale].demo;
  const hydrated = useSyncExternalStore(
    subscribeToHydration,
    clientSnapshot,
    serverSnapshot,
  );
  const [values, setValues] = useState<FormValues>(EMPTY_VALUES);
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [review, setReview] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
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
    setReview(true);
    requestAnimationFrame(() => reviewHeading.current?.focus());
  }

  function edit(): void {
    setReview(false);
    requestAnimationFrame(() =>
      (
        form.current?.elements.namedItem("name") as HTMLInputElement | null
      )?.focus(),
    );
  }

  return (
    <div className={styles.formArea}>
      <p className={styles.localNotice} id="demo-local-notice">
        <Info size={19} aria-hidden="true" />
        <span>{copy.notice}</span>
      </p>
      {review ? (
        <section className={styles.review} aria-labelledby="demo-review-title">
          <h2 id="demo-review-title" ref={reviewHeading} tabIndex={-1}>
            {copy.reviewTitle}
          </h2>
          <p>{copy.reviewBody}</p>
          <dl>
            {([...REQUIRED_FIELDS, "description"] as const).map((field) => (
              <div key={field}>
                <dt>{copy[field]}</dt>
                <dd>{values[field].trim() || copy.empty}</dd>
              </div>
            ))}
          </dl>
          <button type="button" className={styles.button} onClick={edit}>
            <Pencil size={16} aria-hidden="true" />
            {copy.edit}
          </button>
        </section>
      ) : (
        <form
          ref={form}
          onSubmit={submit}
          noValidate
          aria-describedby="demo-local-notice demo-privacy"
          className={styles.demoForm}
        >
          <noscript>
            <p className={styles.localNotice}>{copy.noScript}</p>
          </noscript>
          <fieldset className={styles.formFields} disabled={!hydrated}>
            {REQUIRED_FIELDS.map((field) => (
              <div className={styles.field} key={field}>
                <label htmlFor={`demo-${field}`}>{copy[field]}</label>
                <input
                  id={`demo-${field}`}
                  name={field}
                  type={field === "email" ? "email" : "text"}
                  autoComplete={field}
                  maxLength={field === "email" ? 254 : 120}
                  required
                  placeholder={copy[`${field}Placeholder`]}
                  value={values[field]}
                  aria-invalid={!!errors[field]}
                  aria-describedby={
                    errors[field] ? `demo-${field}-error` : undefined
                  }
                  onChange={(event) => {
                    setValues({ ...values, [field]: event.target.value });
                    if (errors[field])
                      setErrors({ ...errors, [field]: undefined });
                  }}
                />
                {errors[field] && (
                  <p id={`demo-${field}-error`} className={styles.fieldError}>
                    {errors[field]}
                  </p>
                )}
              </div>
            ))}
            <div className={styles.field}>
              <label htmlFor="demo-description">
                {copy.description} <span>{copy.optional}</span>
              </label>
              <textarea
                id="demo-description"
                name="description"
                rows={4}
                maxLength={1000}
                placeholder={copy.descriptionPlaceholder}
                value={values.description}
                onChange={(event) =>
                  setValues({ ...values, description: event.target.value })
                }
              />
            </div>
            {Object.keys(errors).some((field) => errors[field as Field]) && (
              <p className={styles.srOnly} role="alert">
                {copy.errors}
              </p>
            )}
            <button
              type="submit"
              disabled={!hydrated}
              className={styles.button}
            >
              {copy.submit}
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </fieldset>
        </form>
      )}
      <p id="demo-privacy" className={styles.formPrivacy}>
        {copy.privacy}
      </p>
    </div>
  );
}
