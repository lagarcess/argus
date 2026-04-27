"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { getSupabaseClient } from "@/lib/supabase-client";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";

export default function LoginPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = getSupabaseClient();
    if (!supabase) {
      setError(t("auth.login.errors.supabase_not_configured", "Supabase auth is not configured."));
      setLoading(false);
      return;
    }

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
    } else {
      router.replace("/chat");
      router.refresh();
    }
  };

  return (
    <OnboardingGate postCompleteHref="/chat">
      <main className="flex min-h-[100dvh] w-full flex-col items-center justify-center bg-background px-4 py-8">
        <div className="w-full max-w-sm space-y-8">
          <div className="text-center">
            <h1 className="text-4xl font-medium tracking-tight text-foreground">
              {t("auth.login.brand", "argus")}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("auth.login.subtitle", "Sign in to continue")}
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("auth.login.email_placeholder", "Email address")}
                required
                className="w-full rounded-md border border-input bg-transparent px-4 py-3 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("auth.login.password_placeholder", "Password")}
                required
                className="w-full rounded-md border border-input bg-transparent px-4 py-3 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            {error && (
              <p className="text-sm font-medium text-destructive">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-[9999px] bg-primary px-[32px] py-[14px] text-[16px] font-medium text-primary-foreground transition-opacity hover:opacity-85 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-ring disabled:opacity-50"
            >
              {loading
                ? t("auth.login.loading", "Signing in...")
                : t("auth.login.submit", "Sign In")}
            </button>
          </form>
        </div>
      </main>
    </OnboardingGate>
  );
}
