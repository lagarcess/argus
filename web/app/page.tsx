"use client";

export const dynamic = "force-dynamic";

import { useEffect, useRef, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { HeroSection } from "@/components/HeroSection";
import { AuthPanel, AuthPanelHandle } from "@/components/AuthPanel";
import { useAuth } from "@/components/AuthContext";
import { useRouter } from "next/navigation";

export default function LandingPage() {
  const authPanelRef = useRef<AuthPanelHandle>(null);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    const handleHash = () => {
      const hash = window.location.hash;
      if (hash === "#login") {
        authPanelRef.current?.setMode("login");
        authPanelRef.current?.scrollIntoView();
      } else if (hash === "#signup") {
        authPanelRef.current?.setMode("signup");
        authPanelRef.current?.scrollIntoView();
      }
    };

    handleHash();
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  // Redirect if authenticated
  useEffect(() => {
    if (!authLoading && user) {
      router.push("/dashboard");
    }
  }, [user, authLoading, router]);

  const handleActionClick = () => {
    authPanelRef.current?.setMode("signup");
    authPanelRef.current?.scrollIntoView();
  };

  const handleSignInClick = () => {
    authPanelRef.current?.setMode("login");
    authPanelRef.current?.scrollIntoView();
  };

  if (!mounted) return null;

  return (
    <div className="flex flex-col min-h-screen">
      <TopNav onSignInClick={handleSignInClick} />

      <main className="flex-1 pt-32 pb-12 px-6 lg:px-12 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24 items-center">
        <HeroSection onActionClick={handleActionClick} />
        <AuthPanel ref={authPanelRef} />
      </main>

      <footer className="mt-auto px-6 py-8 border-t border-neutral-800/50 flex flex-col md:flex-row justify-between items-center gap-4 text-[10px] tracking-wider uppercase opacity-50">
        <div>© 2026 ARGUS QUANTITATIVE. ALL RIGHTS RESERVED.</div>
        <div className="font-bold text-error">
          SIMULATION ONLY. NO ACTUAL FUNDS AT RISK.
        </div>
      </footer>
    </div>
  );
}
