"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, LayoutDashboard, Search, History, User, Crown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import React, { useState, useEffect } from "react";
// In a real app we'd fetch the generated OpenAPI via lib/api
import { getAuthSessionOptions } from "@/lib/api/@tanstack/react-query.gen";

function QuotaBadge({ remaining, isAdmin }: { remaining: number; isAdmin: boolean }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div className="w-[84px] h-[24px] rounded-full bg-slate-800/50 animate-pulse border border-slate-700/50" />
    );
  }

  if (isAdmin) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-400/30 text-violet-400 text-xs font-semibold shadow-[0_0_10px_rgba(139,92,246,0.2)]">
        <Crown size={12} />
        Admin
      </div>
    );
  }

  const isLow = remaining < 5;
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold ${
       isLow ? "bg-red-500/10 border-red-500/30 text-red-400" : "bg-cyan-500/10 border-cyan-400/30 text-cyan-400"
    }`}>
      {remaining} / 50 Quota
    </div>
  );
}

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const pathname = usePathname();
  const router = useRouter();

  // Middleware handles the secure boundary check, preventing screen flashing.

  const { data: sessionData } = useQuery(getAuthSessionOptions());
  useEffect(() => {
    if (!sessionData) return;
    if (!sessionData.onboarding_completed && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
    if (sessionData.onboarding_completed && pathname === "/onboarding") {
      const search = typeof window !== "undefined" ? window.location.search : "";
      router.replace(`/builder${search}`);
    }
  }, [pathname, router, sessionData]);

  const navLinks = [
    { name: "Builder", href: "/builder", icon: LayoutDashboard },
    { name: "Strategies", href: "/strategies", icon: Search },
    { name: "History", href: "/history", icon: History },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 pb-20 md:pb-0">
      {/* Top Bar (Desktop & Mobile) */}
      <header className="sticky top-0 z-50 glass-nav px-6 py-4 flex items-center justify-between shadow-sm">
        <Link href="/builder" className="flex items-center gap-2 group">
          <Activity className="h-6 w-6 text-cyan-400 group-hover:text-emerald-400 transition-colors" />
          <span className="text-lg font-bold tracking-widest text-slate-100 uppercase hidden sm:block">Argus</span>
        </Link>

        {/* Desktop Nav (≥768px) */}
        <div className="hidden md:flex items-center space-x-6 absolute left-1/2 -translate-x-1/2">
          {navLinks.map((link) => {
            const isActive = pathname.startsWith(link.href);
            return (
              <Link
                key={link.name}
                href={link.href}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full transition-all ${
                  isActive
                    ? "bg-slate-800 text-cyan-400 border border-slate-700 shadow-[0_0_15px_rgba(0,240,255,0.1)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <link.icon size={14} className={isActive ? "drop-shadow-[0_0_8px_rgba(0,240,255,0.8)]" : ""} />
                <span className="text-xs uppercase tracking-widest font-semibold">{link.name}</span>
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-4">
          <QuotaBadge
             remaining={sessionData?.remaining_quota ?? 0}
             isAdmin={sessionData?.is_admin ?? false}
          />
          {mounted ? (
          <Link href="/profile" className="relative group cursor-pointer">
            <div className={`absolute -inset-1 rounded-full blur-md opacity-30 group-hover:opacity-60 transition duration-500 ${
              sessionData?.subscription_tier === 'max' ? "bg-violet-500" :
              sessionData?.subscription_tier === 'pro' ? "bg-amber-500" :
              sessionData?.subscription_tier === 'plus' ? "bg-emerald-400" :
              "bg-cyan-400"
            }`} />
            <div className={`relative w-8 h-8 rounded-full flex items-center justify-center bg-slate-900 border ${
               sessionData?.subscription_tier === 'max' ? "border-violet-500/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]" :
               sessionData?.subscription_tier === 'pro' ? "border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]" :
               sessionData?.subscription_tier === 'plus' ? "border-emerald-400/50 shadow-[0_0_15px_rgba(52,211,153,0.3)]" :
               "border-cyan-400/50 shadow-[0_0_15px_rgba(34,211,238,0.3)]"
            }`}>
               <User size={16} className={
                 sessionData?.subscription_tier === 'max' ? "text-violet-400" :
                 sessionData?.subscription_tier === 'pro' ? "text-amber-400" :
                 sessionData?.subscription_tier === 'plus' ? "text-emerald-400" :
                 "text-cyan-400"
               } />
            </div>
          </Link>
          ) : (
            <div className="relative w-8 h-8 rounded-full bg-slate-800/50 animate-pulse border border-slate-700/50" />
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-x-hidden pt-4 md:pt-8 px-4 md:px-8 max-w-7xl mx-auto w-full">
         {children}
      </main>

      {/* Touch-optimized Bottom Nav (<768px explicitly) */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 glass-nav h-20 px-6 flex items-center justify-between pb-safe z-50">
         {navLinks.map((link) => {
           const isActive = pathname.startsWith(link.href);
           return (
             <Link
                key={link.name}
                href={link.href}
                className={`flex flex-col items-center justify-center w-full h-full gap-1 transition-colors ${
                   isActive ? "text-cyan-400" : "text-slate-500 hover:text-slate-300"
                }`}
             >
                <link.icon size={20} className={isActive ? "drop-shadow-[0_0_8px_rgba(0,240,255,0.8)]" : ""} />
                <span className="text-[10px] uppercase tracking-wider font-semibold">{link.name}</span>
             </Link>
           );
         })}
      </nav>
    </div>
  );
}
