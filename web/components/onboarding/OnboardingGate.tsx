"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/navigation";
import { ChevronRight, Globe } from "lucide-react";
import { getMe, patchMe, ApiUser } from "@/lib/argus-api";
import { DevModeBadge } from "@/components/ui/DevModeBadge";

const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es-419", name: "Español" }
];

const GOAL_IDS = [
  "learn_basics",
  "build_passive_strategy",
  "test_stock_idea",
  "explore_crypto"
] as const;

export function OnboardingGate({
  children,
  postCompleteHref,
}: {
  children: React.ReactNode;
  postCompleteHref?: string;
}) {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [user, setUser] = useState<ApiUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [step, setStep] = useState<"language" | "goal" | "done" | "error">("language");
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);

  useEffect(() => {
    const currentLang = i18n.language;
    if (currentLang.startsWith('es')) {
      setSelectedLanguage('es-419');
    } else if (currentLang.startsWith('en')) {
      setSelectedLanguage('en');
    }
  }, [i18n.language]);

  useEffect(() => {
    async function checkUser() {
      try {
        const me = await getMe();
        setUser(me.user);
        if (me.user.onboarding.completed) {
          setStep("done");
        } else {
          setStep(me.user.onboarding.stage === "primary_goal_selection" ? "goal" : "language");
        }
      } catch (err: any) {
        const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
        
        if (!isMockAuth && (err.status === 401 || err.status === 403)) {
          setUser(null);
          setStep("done");
        } else {
          console.error("Argus API is unreachable or returned an error:", err);
          setStep("error");
        }
      } finally {
        setIsLoading(false);
      }
    }
    checkUser();
  }, []);

  useEffect(() => {
    const isPreview = new URLSearchParams(window.location.search).get("preview") === "true";
    if (!isPreview && user && step === "done" && postCompleteHref) {
      router.replace(postCompleteHref);
    }
  }, [postCompleteHref, router, step, user]);

  const handleLanguageSelect = async (code: string) => {
    setSelectedLanguage(code);
    await i18n.changeLanguage(code);
  };

  const handleConfirmLanguage = async () => {
    if (!selectedLanguage) return;
    try {
      const response = await patchMe({
        language: selectedLanguage as "en" | "es-419",
        onboarding: {
          stage: "primary_goal_selection",
          language_confirmed: true,
          completed: false,
          primary_goal: user?.onboarding.primary_goal || null
        }
      });
      setUser(response.user);
      setStep("goal");
    } catch (err) {
      console.error("Failed to update language:", err);
    }
  };

  const handleGoalSelect = async (goal: string) => {
    try {
      const response = await patchMe({
        onboarding: {
          stage: "ready",
          language_confirmed: true,
          primary_goal: goal as any,
          completed: true
        }
      });
      setUser(response.user);
      setStep("done");
    } catch (err) {
      console.error("Failed to update goal:", err);
    }
  };

  const isPreview = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("preview") === "true";

  if (isLoading && !isPreview) {
    return (
      <>
        <DevModeBadge />
        <div className="flex h-[100dvh] w-full items-center justify-center bg-background">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      </>
    );
  }

  if (step === "done" || isPreview) {
    if (!isPreview && user && postCompleteHref) return null;
    return (
      <>
        <DevModeBadge />
        {children}
      </>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-white dark:bg-[#141517] p-6 text-black dark:text-white transition-colors duration-300">
      <DevModeBadge />
      <div className="w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-500">
        <h1 className="mb-2 text-4xl font-medium tracking-tight">argus</h1>
        
        {step === "language" && (
          <div className="mt-8 space-y-6">
            <div>
              <h2 className="text-xl font-medium">
                {t('onboarding.language.title', 'Choose your language')}
              </h2>
              <p className="mt-1 text-sm text-black/50 dark:text-white/50">
                {t('onboarding.language.subtitle', 'Argus speaks multiple languages. Which one do you prefer?')}
              </p>
            </div>
            
            <div className="grid gap-3">
              {LANGUAGES.map((lang) => {
                const isSelected = selectedLanguage === lang.code;
                return (
                  <button
                    key={lang.code}
                    onClick={() => handleLanguageSelect(lang.code)}
                    className={`group flex items-center justify-between rounded-2xl border p-4 text-left transition-all ${
                      isSelected 
                        ? 'border-[#494fdf] bg-[#494fdf]/[0.02] dark:bg-[#494fdf]/[0.05]' 
                        : 'border-black/5 bg-black/[0.02] hover:bg-black/[0.05] dark:border-white/5 dark:bg-white/[0.02] dark:hover:bg-white/[0.05]'
                    }`}
                  >
                    <div className="flex flex-col">
                      <span className="text-[16px] font-medium">{lang.name}</span>
                      <span className="text-[13px] text-black/40 dark:text-white/40">{t(`onboarding.language.${lang.code}`)}</span>
                    </div>
                    <ChevronRight className={`w-5 h-5 transition-all ${isSelected ? 'text-[#494fdf] translate-x-0.5' : 'text-black/20 dark:text-white/20 group-hover:translate-x-0.5'}`} />
                  </button>
                );
              })}
            </div>

            <button
              onClick={handleConfirmLanguage}
              disabled={!selectedLanguage}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-[9999px] bg-[#191c1f] dark:bg-white px-[32px] py-[14px] text-[16px] font-medium text-white dark:text-black transition-all hover:opacity-85 disabled:opacity-50"
            >
              {selectedLanguage 
                ? t('onboarding.language.continue_in', { language: LANGUAGES.find(l => l.code === selectedLanguage)?.name })
                : t('common.submit', 'Submit')
              }
            </button>
          </div>
        )}

        {step === "goal" && (
          <div className="mt-8 space-y-6">
            <div>
              <h2 className="text-xl font-medium">
                {t('onboarding.primary_goal', 'What is your primary goal?')}
              </h2>
              <p className="mt-1 text-sm text-black/50 dark:text-white/50">
                {t('onboarding.goal_description', "We'll tailor your strategy insights based on this.")}
              </p>
            </div>

            <div className="grid gap-3">
              {GOAL_IDS.map((goalId) => (
                <button
                  key={goalId}
                  onClick={() => handleGoalSelect(goalId)}
                  className="group flex items-center justify-between rounded-2xl border border-black/5 bg-black/[0.02] p-4 text-left transition-all hover:bg-black/[0.05] dark:border-white/5 dark:bg-white/[0.02] dark:hover:bg-white/[0.05]"
                >
                  <div className="flex flex-col">
                    <span className="text-[16px] font-medium">{t(`onboarding.goals.${goalId}.title`)}</span>
                    <span className="text-[13px] text-black/40 dark:text-white/40">{t(`onboarding.goals.${goalId}.description`)}</span>
                  </div>
                  <ChevronRight className="w-5 h-5 text-black/20 dark:text-white/20 transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
              <button
                onClick={() => handleGoalSelect("surprise_me")}
                className="mt-2 text-center text-[13px] font-medium text-black/40 underline-offset-4 hover:text-black hover:underline dark:text-white/40 dark:hover:text-white"
              >
                {t('onboarding.skip', 'Skip for now')}
              </button>
            </div>
          </div>
        )}
        {step === "error" && (
          <div className="mt-8 space-y-6">
            <div className="rounded-2xl border border-red-500/10 bg-red-500/[0.02] p-6 text-center dark:border-red-500/20 dark:bg-red-500/[0.05]">
              <h2 className="text-xl font-medium text-red-600 dark:text-red-400">
                {t('onboarding.error.title', 'API Unreachable')}
              </h2>
              <p className="mt-2 text-sm text-black/50 dark:text-white/50">
                {t('onboarding.error.description', "We couldn't connect to the Argus engine. Please ensure the backend service is running and try again.")}
              </p>
              <button
                onClick={() => window.location.reload()}
                className="mt-6 w-full rounded-xl bg-black px-4 py-3 text-[15px] font-medium text-white transition-opacity hover:opacity-90 dark:bg-white dark:text-black"
              >
                {t('onboarding.error.retry', 'Try Again')}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
