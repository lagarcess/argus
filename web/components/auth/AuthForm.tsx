"use client";

import { type FormEvent, useState } from "react";
import { Eye, EyeClosed } from "lucide-react";
import { useTranslation } from "react-i18next";
import { blockingErrorBannerClass } from "@/lib/failure-treatment";

export type AuthFormMode = "login" | "signup";

export type AuthFormSubmission = {
  mode: AuthFormMode;
  displayName: string;
  email: string;
  password: string;
};

type AuthFormProps = {
  mode: AuthFormMode;
  allowModeSwitch?: boolean;
  onModeChange?: (mode: AuthFormMode) => void;
  onSubmit: (submission: AuthFormSubmission) => Promise<void>;
};

export default function AuthForm({
  mode,
  allowModeSwitch = true,
  onModeChange,
  onSubmit,
}: AuthFormProps) {
  const { t } = useTranslation();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSignup = mode === "signup";

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError(null);
    setIsSubmitting(true);
    try {
      await onSubmit({
        mode,
        displayName: displayName.trim(),
        email: email.trim(),
        password,
      });
    } catch (error) {
      setAuthError(
        error instanceof Error
          ? error.message
          : t("auth.errors.generic", "Something went wrong. Please try again."),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit} className="space-y-3">
        {isSignup && (
          <input
            type="text"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={t("auth.signup.name_placeholder", "Name")}
            autoComplete="name"
            className="w-full rounded-[20px] border border-black/15 bg-transparent px-5 py-[14px] text-[16px] tracking-[0.16px] text-black transition-colors placeholder:text-black/40 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus-visible:ring-white"
          />
        )}

        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={t("auth.login.email_placeholder", "Email address")}
          autoComplete="email"
          required
          autoFocus
          className="w-full rounded-[20px] border border-black/15 bg-transparent px-5 py-[14px] text-[16px] tracking-[0.16px] text-black transition-colors placeholder:text-black/40 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus-visible:ring-white"
        />

        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={t("auth.login.password_placeholder", "Password")}
            autoComplete={isSignup ? "new-password" : "current-password"}
            required
            minLength={isSignup ? 8 : undefined}
            className="w-full rounded-[20px] border border-black/15 bg-transparent px-5 py-[14px] pr-14 text-[16px] tracking-[0.16px] text-black transition-colors placeholder:text-black/40 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus-visible:ring-white"
          />
          <button
            type="button"
            aria-label={
              showPassword
                ? t("auth.password.hide", "Hide password")
                : t("auth.password.show", "Show password")
            }
            onClick={() => setShowPassword((visible) => !visible)}
            className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full text-black/45 transition-colors hover:bg-black/5 hover:text-black focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:text-white/45 dark:hover:bg-white/10 dark:hover:text-white dark:focus-visible:ring-white"
          >
            {showPassword ? (
              <EyeClosed className="h-5 w-5" />
            ) : (
              <Eye className="h-5 w-5" />
            )}
          </button>
        </div>

        {!isSignup && (
          <a
            href="/auth/forgot-password"
            className="block px-1 text-right text-sm font-medium text-black/60 transition-opacity hover:opacity-75 dark:text-white/60"
          >
            {t("auth.recovery.forgot", "Forgot password?")}
          </a>
        )}

        {authError && (
          <p role="alert" className={blockingErrorBannerClass}>
            {authError}
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="font-display flex w-full items-center justify-center rounded-[9999px] bg-black px-[32px] py-[14px] text-[16px] font-medium text-white transition-opacity hover:opacity-85 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black disabled:opacity-50 dark:bg-white dark:text-black dark:focus-visible:ring-white"
        >
          {isSubmitting
            ? isSignup
              ? t("auth.signup.loading", "Creating account...")
              : t("auth.login.loading", "Signing in...")
            : isSignup
              ? t("auth.signup.submit", "Sign up")
              : t("auth.login.submit", "Sign In")}
        </button>
      </form>

      {allowModeSwitch && onModeChange && (
        <p className="mt-5 text-center text-[15px] tracking-wide text-gray-500 dark:text-gray-400">
          {isSignup
            ? t("landing.already_account", "Already have an account?")
            : t("auth.signup.new_account", "New to Argus?")}{" "}
          <button
            type="button"
            className="font-medium text-black transition-opacity hover:opacity-80 dark:text-white"
            onClick={() => onModeChange(isSignup ? "login" : "signup")}
          >
            {isSignup
              ? t("landing.sign_in", "Sign in")
              : t("auth.signup.submit", "Sign up")}
          </button>
        </p>
      )}

      <p className="mt-5 w-full px-4 text-center text-[11px] tracking-tight text-zinc-500 md:text-[12px]">
        {isSignup
          ? t("landing.legal_prefix", "By signing up, you agree to our")
          : t(
              "auth.legal.continuing_prefix",
              "By continuing, you agree to our",
            )}{" "}
        <a
          href="/terms"
          className="font-semibold text-zinc-800 transition-colors hover:text-black dark:text-zinc-400 dark:hover:text-white"
        >
          {t("landing.terms", "Terms")}
        </a>{" "}
        {t("common.and", "and")}{" "}
        <a
          href="/privacy"
          className="font-semibold text-zinc-800 transition-colors hover:text-black dark:text-zinc-400 dark:hover:text-white"
        >
          {t("landing.privacy", "Privacy Policy")}
        </a>
        .
      </p>
    </div>
  );
}
