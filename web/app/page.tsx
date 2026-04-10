"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Activity, Shield, Zap, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import { AuthPanel, AuthPanelHandle } from "@/components/AuthPanel";
import { NebulaBackground } from "@/components/NebulaTransition";
import { useAuth } from "@/components/AuthContext";
import { useRouter } from "next/navigation";
import Link from "next/link";

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

  // Redirect if authenticated - matching old routing but mapped to new protected area
  useEffect(() => {
    if (!authLoading && user) {
      router.push("/builder");
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
    <div className="min-h-screen bg-slate-950 flex flex-col relative overflow-hidden">
      {/* Abstract Background Glows & Interactive Nebula */}
      <div className="absolute top-0 inset-x-0 h-[500px] bg-cyan-500/10 blur-[120px] rounded-full pointer-events-none transform -translate-y-1/2" />
      <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-emerald-500/10 blur-[120px] rounded-full pointer-events-none transform translate-y-1/2" />
      <NebulaBackground className="opacity-40" />

      {/* Top Nav */}
      <nav className="w-full px-6 py-4 flex items-center justify-between z-10 glass-nav relative">
        <div className="flex items-center gap-2">
          <Activity className="h-6 w-6 text-cyan-400" />
          <span className="text-lg font-bold tracking-widest text-slate-100 uppercase">Argus</span>
        </div>
        <button
          onClick={handleSignInClick}
          className="btn-secondary text-sm"
        >
          Sign In
        </button>
      </nav>

      {/* Hero Section + Auth Panel Split */}
      <main className="flex-1 px-6 z-10 pt-12 pb-24 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24 items-center">

        {/* Left Side: The New Dribbble Hero text */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="space-y-8"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-cyan-400/30 text-cyan-400 text-xs font-semibold tracking-widest uppercase mb-4">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            Private Beta
          </div>

          <h1 className="text-5xl md:text-7xl font-black text-slate-100 tracking-tight leading-tight">
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-emerald-400">Backtesting.</span> <br className="hidden md:block"/>
            Narrow the Reality Gap.
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-xl leading-relaxed">
            Mobile-first for retail traders. Test and refine your ideas in a real-feel environment — spot the gaps, understand why, and build stronger strategies before going live.
          </p>

          <div className="pt-4 pb-8 border-b border-slate-800/50">
            <button
              onClick={handleActionClick}
              className="btn-primary text-lg px-8 py-4 flex items-center gap-2 uppercase tracking-wide shadow-cyan-400/20 shadow-lg"
            >
              Run Your Strategy <ArrowRight className="h-5 w-5" />
            </button>
            <p className="text-xs text-slate-500 mt-3 font-semibold uppercase tracking-widest pl-2">Start for free. No credit card required.</p>
          </div>

          {/* Features Grid inline */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left mt-8">
            {[
              { icon: Shield, title: "Institutional-Grade Accuracy", desc: "Rigorous reality-gap constraints including execution slippage." },
              { icon: Zap, title: "Sync Execution", desc: "Clustered engine completes single-symbol backtests in under 3s." }
            ].map((f, i) => (
              <div key={i} className="flex gap-4 items-start group">
                <div className="w-10 h-10 rounded-xl bg-slate-900 border border-cyan-400/20 flex flex-shrink-0 items-center justify-center group-hover:bg-cyan-400/10 transition-colors">
                  <f.icon className="h-5 w-5 text-cyan-400" />
                </div>
                <div>
                    <h3 className="text-sm font-bold text-slate-100 mb-1">{f.title}</h3>
                    <p className="text-slate-500 leading-relaxed text-xs">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Right Side: The Old Auth Panel */}
        <motion.div
           initial={{ opacity: 0, x: 20 }}
           animate={{ opacity: 1, x: 0 }}
           transition={{ duration: 0.6, delay: 0.2 }}
        >
          <AuthPanel ref={authPanelRef} />
        </motion.div>

      </main>
    </div>
  );
}
