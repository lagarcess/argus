"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SettingsMenu } from "@/components/SettingsMenu";
import { useTranslation } from "react-i18next";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";
import AuthForm, {
  type AuthFormMode,
  type AuthFormSubmission,
} from "@/components/auth/AuthForm";
import {
  loginWithEmail,
  normalizeApiLanguage,
  signupWithEmail,
} from "@/lib/argus-api";

type AuthMode = "intro" | "signup" | "login";

function authModeFromLocation(): AuthMode {
  if (typeof window === "undefined") return "intro";
  const mode = new URLSearchParams(window.location.search).get("auth");
  return mode === "signup" || mode === "login" ? mode : "intro";
}

export default function AuthLanding() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const [authMode, setAuthMode] = useState<AuthMode>("intro");

  useEffect(() => {
    setAuthMode(authModeFromLocation());
  }, []);

  const updateAuthMode = (nextMode: AuthMode) => {
    setAuthMode(nextMode);
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

  const handleAuthSubmit = async (submission: AuthFormSubmission) => {
    if (isMockAuth) {
      router.replace("/chat");
      router.refresh();
      return;
    }
    if (submission.mode === "signup") {
      await signupWithEmail({
        email: submission.email,
        password: submission.password,
        language: normalizeApiLanguage(i18n.resolvedLanguage ?? i18n.language),
        display_name: submission.displayName || null,
      });
    } else {
      await loginWithEmail({
        email: submission.email,
        password: submission.password,
      });
    }
    router.replace("/chat");
    router.refresh();
  };

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
            <div className="w-full max-w-sm">
              <AuthForm
                mode={authMode as AuthFormMode}
                onModeChange={(mode) => updateAuthMode(mode)}
                onSubmit={handleAuthSubmit}
              />
            </div>
          )}

          {authMode === "intro" && (
            <>
              <p className="text-[16px] tracking-wide text-gray-500 dark:text-gray-400">
                {t("landing.already_account")}{" "}
                <button
                  type="button"
                  className="font-medium text-black transition-opacity hover:opacity-80 dark:text-white"
                  onClick={showLogin}
                >
                  {t("landing.sign_in")}
                </button>
              </p>
              <p className="mt-4 w-full px-4 text-center text-[11px] tracking-tight text-zinc-500 md:text-[12px]">
                {t("landing.legal_prefix", "By joining, you agree to our")}{" "}
                <a href="/terms" className="font-semibold text-zinc-800 transition-colors hover:text-black dark:text-zinc-400 dark:hover:text-white">
                  {t("landing.terms")}
                </a>{" "}
                {t("common.and", "and")}{" "}
                <a href="/privacy" className="font-semibold text-zinc-800 transition-colors hover:text-black dark:text-zinc-400 dark:hover:text-white">
                  {t("landing.privacy")}
                </a>
                .
              </p>
            </>
          )}
        </div>
      </main>
    </OnboardingGate>
  );
}
