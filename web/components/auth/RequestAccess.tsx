"use client";

import {
  type FormEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { normalizeApiLanguage } from "@/lib/argus-api";
import { requestAccess } from "@/lib/guest-api";

type RequestAccessProps = {
  headingId?: string;
  embedded?: boolean;
  onShowSignup: () => void;
  onShowLogin: () => void;
};

export default function RequestAccess({
  headingId = "request-access-title",
  embedded = false,
  onShowSignup,
  onShowLogin,
}: RequestAccessProps) {
  const { t, i18n } = useTranslation();
  const emailInputId = useId();
  const acceptedHeadingRef = useRef<HTMLHeadingElement>(null);
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAccepted, setIsAccepted] = useState(false);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    if (isAccepted) acceptedHeadingRef.current?.focus();
  }, [isAccepted]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setHasError(false);
    setIsSubmitting(true);
    try {
      await requestAccess({
        email: email.trim(),
        language: normalizeApiLanguage(
          i18n.resolvedLanguage ?? i18n.language,
        ),
      });
      setIsAccepted(true);
    } catch {
      setHasError(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className={
        embedded
          ? "w-full"
          : "w-full rounded-[20px] border border-black/10 bg-white p-7 dark:border-white/10 dark:bg-[#151719]"
      }
    >
      {isAccepted ? (
        <div role="status" aria-live="polite" className="text-center">
          <h2
            id={headingId}
            ref={acceptedHeadingRef}
            tabIndex={-1}
            className="font-display text-[24px] font-medium tracking-tight text-black outline-none dark:text-white"
          >
            {t("auth.access_request.accepted_title")}
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-black/60 dark:text-white/60">
            {t("auth.access_request.accepted_description")}
          </p>
        </div>
      ) : (
        <>
          <div className="mb-6 text-center">
            <h2
              id={headingId}
              className="font-display text-[24px] font-medium tracking-tight text-black dark:text-white"
            >
              {t("auth.access_request.title")}
            </h2>
            <p className="mt-3 text-[15px] leading-relaxed text-black/60 dark:text-white/60">
              {t("auth.access_request.description")}
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-3">
            <label htmlFor={emailInputId} className="sr-only">
              {t("auth.access_request.email_label")}
            </label>
            <input
              id={emailInputId}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder={t("auth.access_request.email_label")}
              autoComplete="email"
              required
              autoFocus
              className="w-full rounded-[20px] border border-black/15 bg-transparent px-5 py-[14px] text-[16px] tracking-[0.16px] text-black transition-colors placeholder:text-black/40 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus-visible:ring-white"
            />
            {hasError ? (
              <p
                role="alert"
                className="rounded-[20px] border border-red-500/20 bg-red-500/[0.04] px-5 py-3 text-center text-sm font-medium text-red-600 dark:text-red-300"
              >
                {t("auth.access_request.error")}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={isSubmitting}
              className="font-display flex min-h-11 w-full items-center justify-center rounded-[9999px] bg-black px-8 py-[14px] text-[16px] font-medium text-white transition-opacity hover:opacity-85 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black disabled:opacity-50 dark:bg-white dark:text-black dark:focus-visible:ring-white"
            >
              {isSubmitting
                ? t("auth.access_request.submitting")
                : t("auth.access_request.submit")}
            </button>
          </form>
        </>
      )}

      <div className="mt-5 space-y-2 text-center text-[15px] tracking-wide text-gray-500 dark:text-gray-400">
        <p>
          {t("auth.access_request.approved_prompt")}{" "}
          <button
            type="button"
            onClick={onShowSignup}
            className="min-h-11 font-medium text-black transition-opacity hover:opacity-80 dark:text-white"
          >
            {t("auth.access_request.approved_action")}
          </button>
        </p>
        <p>
          {t("auth.access_request.existing_prompt")}{" "}
          <button
            type="button"
            onClick={onShowLogin}
            className="min-h-11 font-medium text-black transition-opacity hover:opacity-80 dark:text-white"
          >
            {t("auth.access_request.existing_action")}
          </button>
        </p>
      </div>
    </div>
  );
}
