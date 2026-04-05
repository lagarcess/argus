"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GoogleIcon, AppleIcon, FacebookIcon } from "@/components/Icons";
import { useTheme } from "@/components/ThemeProvider";

export default function LandingPage() {
  const [authMode, setAuthMode] = useState<"login" | "signup">("signup");
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/dashboard");
  };

  const handleSocialAuth = (provider: string) => {
    // Navigate straight to dashboard for now - mock MVP
    router.push("/dashboard");
  };

  return (
    <div className="bg-background text-on-background font-body selection:bg-primary/30 min-h-screen flex flex-col">
      <nav className="fixed top-0 w-full z-50 flex justify-between items-center px-6 py-4 bg-neutral-950/40 backdrop-blur-xl border-b border-neutral-800/50 shadow-[0_20px_40px_rgba(0,0,0,0.4)]">
        <div className="flex items-center gap-2">
          <span className="text-xl font-bold tracking-tighter text-cyan-400 font-headline">
            ARGUS
          </span>
          <span className="hidden md:inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest bg-primary/10 text-primary border border-primary/20">
            OBSIDIAN CORE
          </span>
        </div>

        <div className="hidden md:flex gap-8 text-xs font-bold uppercase tracking-widest text-neutral-400">
          <a href="#" className="hover:text-cyan-300 transition-colors">
            Intelligence
          </a>
          <a href="#" className="hover:text-cyan-300 transition-colors">
            API Documentation
          </a>
          <a href="#" className="hover:text-cyan-300 transition-colors">
            Pricing
          </a>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="p-2 text-neutral-400 hover:text-cyan-300 transition-colors"
            title="Toggle theme"
          >
            <span className="material-symbols-outlined">
              {theme === "dark" ? "light_mode" : "dark_mode"}
            </span>
          </button>
          <button
            onClick={() => {
              setAuthMode("login");
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            className="px-6 py-2 rounded-full border border-neutral-800 hover:border-cyan-400/50 text-xs font-bold uppercase tracking-widest transition-all"
          >
            Access Portal
          </button>
        </div>
      </nav>

      <main className="flex-1 pt-32 pb-12 px-6 lg:px-12 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24 items-center">
        {/* Left Column: Value Prop */}
        <div className="space-y-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-secondary/10 border border-secondary/20 mb-6">
              <span className="w-2 h-2 rounded-full bg-secondary animate-pulse shadow-[0_0_10px_rgba(47,248,1,0.5)]"></span>
              <span className="text-[10px] font-bold text-secondary uppercase tracking-widest">
                System Status: Optimal
              </span>
            </div>
            <h1 className="text-5xl lg:text-7xl font-headline font-black tracking-tighter uppercase leading-[0.9] text-on-surface">
              Find Alpha in the <span className="text-gradient-cyan">Noise</span>
            </h1>
            <p className="mt-6 text-on-surface-variant max-w-lg text-sm md:text-base leading-relaxed">
              ARGUS provides institutional-grade volatility models and high-frequency
              backtesting protocols within the Obsidian environment.
              Deploy simulated strategies without reality gaps.
            </p>
          </div>

          {/* Social Proof / Metrics */}
          <div className="flex gap-8 pt-8 border-t border-neutral-800/50">
            <div>
              <div className="text-3xl font-headline font-black text-on-surface">14.2B</div>
              <div className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
                Nodes Processed
              </div>
            </div>
            <div>
              <div className="text-3xl font-headline font-black text-on-surface">0.1ms</div>
              <div className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
                Simulation Latency
              </div>
            </div>
            <div className="hidden md:block">
              <div className="text-3xl font-headline font-black text-on-surface">99.9%</div>
              <div className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
                Market Accuracy
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Auth Panel */}
        <div className="relative group perspective-1000">
          <div className="absolute inset-0 bg-primary/20 blur-[100px] rounded-full group-hover:bg-primary/30 transition-colors duration-700 pointer-events-none"></div>

          <div className="glass-panel relative z-10 rounded-2xl border border-outline-variant/30 p-8 shadow-2xl transform transition-transform duration-500">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-headline font-bold">
                {authMode === "login" ? "AUTHENTICATE" : "INITIALIZE NODE"}
              </h2>
              <div className="flex bg-surface-container-high rounded-lg p-1">
                <button
                  onClick={() => setAuthMode("signup")}
                  className={`px-4 py-1.5 text-xs font-bold uppercase tracking-widest rounded transition-colors ${
                    authMode === "signup"
                      ? "bg-primary text-on-primary shadow-sm"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  Register
                </button>
                <button
                  onClick={() => setAuthMode("login")}
                  className={`px-4 py-1.5 text-xs font-bold uppercase tracking-widest rounded transition-colors ${
                    authMode === "login"
                      ? "bg-primary text-on-primary shadow-sm"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  Login
                </button>
              </div>
            </div>

            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                  Email Address
                </label>
                <input
                  type="email"
                  className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary transition-all outline-none"
                  placeholder="operator@argus.io"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                  Encryption Key
                </label>
                <input
                  type="password"
                  className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary transition-all outline-none"
                  placeholder="••••••••••••"
                  required
                />
              </div>

              {authMode === "login" && (
                <div className="flex justify-end">
                  <a
                    href="#"
                    className="text-[10px] text-primary hover:text-primary-dim uppercase tracking-widest font-bold"
                  >
                    Forgot Key?
                  </a>
                </div>
              )}

              <button
                type="submit"
                className="w-full py-3.5 mt-4 bg-surface-container-highest border border-outline-variant hover:bg-primary hover:text-on-primary hover:border-primary rounded-xl text-xs font-bold uppercase tracking-widest transition-all shadow-lg flex items-center justify-center gap-2"
              >
                {authMode === "login" ? "Establish Connection" : "Deploy Protocol"}
                <span className="material-symbols-outlined text-sm">
                  arrow_forward
                </span>
              </button>
            </form>

            <div className="my-6 flex items-center gap-4">
              <div className="flex-1 h-px bg-outline-variant/20"></div>
              <span className="text-[10px] uppercase tracking-widest text-on-surface-variant">
                OR BYPASS WITH
              </span>
              <div className="flex-1 h-px bg-outline-variant/20"></div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => handleSocialAuth("google")}
                className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-white hover:border-white group rounded-xl transition-all flex items-center justify-center"
              >
                <GoogleIcon className="w-5 h-5 flex-shrink-0" />
              </button>
              <button
                onClick={() => handleSocialAuth("apple")}
                className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-neutral-800 hover:text-white rounded-xl transition-all flex items-center justify-center group"
              >
                <AppleIcon className="w-5 h-5 text-on-surface group-hover:text-white" />
              </button>
              <button
                onClick={() => handleSocialAuth("facebook")}
                className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-[#1877F2] hover:border-[#1877F2] hover:text-white rounded-xl transition-all flex items-center justify-center group"
              >
                <FacebookIcon className="w-5 h-5 text-[#1877F2] group-hover:text-white" />
              </button>
            </div>

            <p className="mt-6 text-center text-[10px] text-on-surface-variant font-label opacity-70">
              By connecting, you agree to our{" "}
              <a href="#" className="underline">Terms</a> and{" "}
              <a href="#" className="underline">Privacy Doctrine</a>.
            </p>
          </div>
        </div>
      </main>

      <footer className="mt-auto px-6 py-8 border-t border-neutral-800/50 flex flex-col md:flex-row justify-between items-center gap-4 text-[10px] tracking-wider uppercase opacity-50">
        <div>© 2026 ARGUS QUANTITATIVE. REALITY GAP APPLIED.</div>
        <div className="font-bold text-error">
          SIMULATION ONLY. NO ACTUAL FUNDS AT RISK.
        </div>
      </footer>
    </div>
  );
}
