"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeClosed } from "lucide-react";
import { SettingsMenu } from "@/components/SettingsMenu";
import { useTranslation } from "react-i18next";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";
import { loginWithEmail, signupWithEmail } from "@/lib/argus-api";

type AuthMode = "intro" | "signup" | "login";

function authModeFromLocation(): AuthMode {
  if (typeof window === "undefined") return "intro";
  const mode = new URLSearchParams(window.location.search).get("auth");
  return mode === "signup" || mode === "login" ? mode : "intro";
}

export default function LandingPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const [authMode, setAuthMode] = useState<AuthMode>("intro");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setAuthMode(authModeFromLocation());
  }, []);

  const updateAuthMode = (nextMode: AuthMode) => {
    setAuthMode(nextMode);
    setAuthError(null);
    setShowPassword(false);
    if (typeof window === "undefined") return;

    const params = new URLSearchParams(window.location.search);
    if (nextMode === "intro") {
      params.delete("auth");
    } else {
      params.set("auth", nextMode);
    }

    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
    window.history.replaceState(null, "", nextUrl);
  };
  const showSignup = () => updateAuthMode("signup");
  const showLogin = () => updateAuthMode("login");

  const handleAuthSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError(null);
    setIsSubmitting(true);

    try {
      if (isMockAuth) {
        router.replace("/chat");
        router.refresh();
        return;
      }

      if (authMode === "signup") {
        await signupWithEmail({
          email,
          password,
          display_name: displayName.trim() || null,
        });
      } else {
        await loginWithEmail({ email, password });
      }

      router.replace("/chat");
      router.refresh();
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

  const isSignup = authMode === "signup";
  const isLogin = authMode === "login";

  return (
    <OnboardingGate postCompleteHref="/chat">
      <main className="relative flex min-h-[100dvh] w-full flex-col justify-between overflow-hidden px-6 py-8 md:px-12">
        <SettingsMenu />

        <div className="flex flex-grow items-center justify-center">
          <h1 className="font-display text-6xl md:text-[80px] font-medium tracking-tight text-black dark:text-white z-10 select-none transition-colors">
            argus
          </h1>
        </div>

        <div className="relative z-10 flex w-full flex-col items-center gap-6 pb-2 md:pb-4">
          {authMode === "intro" ? (
            <button
              type="button"
              onClick={showSignup}
              className="font-display flex w-full max-w-sm items-center justify-center rounded-[9999px] bg-black px-[32px] py-[14px] text-[16px] font-medium text-white transition-opacity hover:opacity-85 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:bg-white dark:text-black dark:focus-visible:ring-white"
            >
              {t('landing.sign_up_email')}
            </button>
          ) : (
            <form onSubmit={handleAuthSubmit} className="w-full max-w-sm space-y-3">
              {isSignup && (
                <input
                  type="text"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder={t("auth.signup.name_placeholder", "Name")}
                  className="w-full rounded-[20px] border border-black/15 bg-transparent px-5 py-[14px] text-[16px] tracking-[0.16px] text-black transition-colors placeholder:text-black/40 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus-visible:ring-white"
                />
              )}

              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={t("auth.login.email_placeholder", "Email address")}
                required
                className="w-full rounded-[20px] border border-black/15 bg-transparent px-5 py-[14px] text-[16px] tracking-[0.16px] text-black transition-colors placeholder:text-black/40 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:border-white/20 dark:text-white dark:placeholder:text-white/40 dark:focus-visible:ring-white"
              />

              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={t("auth.login.password_placeholder", "Password")}
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
                  {showPassword ? <EyeClosed className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>

              {authError && (
                <p className="rounded-[20px] border border-red-500/20 bg-red-500/[0.04] px-5 py-3 text-center text-sm font-medium text-red-600 dark:text-red-300">
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
          )}

          <p className="text-[16px] tracking-wide text-gray-500 dark:text-gray-400">
            {isLogin
              ? t("auth.signup.new_account", "new to argus?")
              : t('landing.already_account')}{" "}
            <button
              type="button"
              className="font-medium text-black transition-opacity hover:opacity-80 dark:text-white"
              onClick={isLogin ? showSignup : showLogin}
            >
              {isLogin
                ? t("auth.signup.submit", "Sign up")
                : t('landing.sign_in')}
            </button>
          </p>

          <p className="mt-4 w-full px-4 text-center text-[11px] md:text-[12px] text-zinc-500 tracking-tight">
            {t('landing.legal_prefix', 'By joining, you agree to our')}{" "}
            <a href="#" className="font-semibold text-zinc-800 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors">
              {t('landing.terms')}
            </a>{" "}
            {t('common.and', 'and')}{" "}
            <a href="#" className="font-semibold text-zinc-800 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors">
              {t('landing.privacy')}
            </a>.
          </p>
        </div>
      </main>
    </OnboardingGate>
  );
}
