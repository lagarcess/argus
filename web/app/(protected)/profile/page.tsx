"use client";


import { User, Shield, LogOut, Zap, Globe, Moon, Sun, Monitor, Check } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { useRouter } from "next/navigation";
import { useState } from "react";
// In real app, import from lib/api
import { getAuthSessionOptions } from "@/lib/api/@tanstack/react-query.gen";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const NEUTRAL_AVATARS = [
  "bg-gradient-to-br from-cyan-400 to-blue-600",
  "bg-gradient-to-br from-emerald-400 to-cyan-600",
  "bg-gradient-to-br from-purple-500 to-indigo-600",
  "bg-gradient-to-br from-orange-400 to-red-500",
];

function PricingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [isAnnual, setIsAnnual] = useState(true);

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="glass-card max-w-5xl w-full border-slate-700 p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 hover:text-slate-100">✕</button>

        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold tracking-tight text-slate-100">Upgrade Your Plan</h2>
          <p className="text-slate-400 mt-2">Select a paid plan to unlock premium features.</p>

          {/* Billing Toggle */}
          <div className="flex items-center justify-center gap-3 mt-8">
            <span className={`text-sm font-semibold transition-colors ${!isAnnual ? "text-slate-100" : "text-slate-500"}`}>Monthly</span>
            <button
              onClick={() => setIsAnnual(!isAnnual)}
              className="w-14 h-7 bg-slate-800 rounded-full relative border border-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            >
              <div className={cn(
                "absolute top-1 left-1 w-5 h-5 rounded-full bg-cyan-400 transition-transform duration-300",
                isAnnual ? "translate-x-7" : "translate-x-0"
              )} />
            </button>
            <span className={`text-sm font-semibold transition-colors flex items-center gap-2 ${isAnnual ? "text-slate-100" : "text-slate-500"}`}>
              Annually <span className="bg-emerald-500/20 text-emerald-400 text-[10px] px-2 py-0.5 rounded-full border border-emerald-400/30">SAVE 20%</span>
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Free */}
          <div className="border border-cyan-400/20 rounded-2xl p-6 relative bg-slate-900/50 transition-all hover:border-cyan-400/40 hover:bg-cyan-950/5">
            <h3 className="text-xl font-bold text-cyan-400 text-center">Free</h3>
            <p className="text-[10px] uppercase tracking-widest text-cyan-500/70 text-center mt-1">Try Argus</p>
            <div className="my-4 h-[60px] text-center">
              <p className="text-3xl font-black text-slate-100">$0 <span className="text-sm font-normal text-slate-400">/mo</span></p>
              <p className="text-[10px] text-slate-500 lowercase tracking-widest mt-1">Free for everyone</p>
            </div>
            <ul className="space-y-3 mb-8 text-sm text-slate-300">
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-cyan-400" /> 50 executions/mo</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-cyan-400" /> Single-asset testing</li>
            </ul>
            <button className="w-full btn-secondary text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/10 py-2" onClick={onClose}>Current Plan</button>
          </div>

          {/* Plus */}
          <div className="border border-emerald-400/30 rounded-2xl p-6 relative bg-slate-900/50 transition-all hover:border-emerald-400/50 hover:bg-emerald-950/10">
            <h3 className="text-xl font-bold text-emerald-400 text-center">Plus</h3>
            <p className="text-[10px] uppercase tracking-widest text-emerald-500/70 text-center mt-1">For Active Traders</p>
            <div className="my-4 h-[60px] text-center">
              <p className="text-3xl font-black text-slate-100">${isAnnual ? "19" : "24"} <span className="text-sm font-normal text-slate-400">/mo</span></p>
              {isAnnual && <p className="text-[10px] text-slate-500 lowercase tracking-widest mt-1">Billed $228 annually</p>}
            </div>
            <ul className="space-y-3 mb-8 text-sm text-slate-300">
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-emerald-400" /> 500 executions/mo</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-emerald-400" /> Multi-asset testing</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-emerald-400" /> Basic Indicators</li>
            </ul>
            <button className="w-full btn-secondary text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10 py-2" onClick={onClose}>Upgrade to Plus</button>
          </div>

          {/* Pro */}
          <div className="border border-amber-500/50 rounded-2xl p-6 relative bg-amber-950/20 shadow-[0_0_30px_rgba(245,158,11,0.1)] transition-all hover:border-amber-400/70">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-amber-500 text-slate-950 text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest">Recommended</div>
            <h3 className="text-xl font-bold text-amber-500 text-center">Pro</h3>
            <p className="text-[10px] uppercase tracking-widest text-amber-500/70 text-center mt-1">For Advanced Traders</p>
            <div className="my-4 h-[60px] text-center">
              <p className="text-3xl font-black text-slate-100">${isAnnual ? "49" : "59"} <span className="text-sm font-normal text-slate-400">/mo</span></p>
              {isAnnual && <p className="text-[10px] text-slate-500 lowercase tracking-widest mt-1">Billed $588 annually</p>}
            </div>
            <ul className="space-y-3 mb-8 text-sm text-slate-300">
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-amber-500" /> Unlimited executions</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-amber-500" /> API Access</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-amber-500" /> Premium Indicators</li>
            </ul>
            <button className="w-full btn-primary bg-amber-500 hover:bg-amber-400 text-slate-900 py-2" onClick={onClose}>Upgrade to Pro</button>
          </div>

          {/* Max */}
          <div className="border border-violet-500/30 rounded-2xl p-6 relative bg-slate-900/50 shadow-[0_0_15px_rgba(139,92,246,0.05)] transition-all hover:bg-violet-950/10 hover:border-violet-500/50">
            <h3 className="text-xl font-bold text-violet-400 text-center">Max</h3>
            <p className="text-[10px] uppercase tracking-widest text-violet-500/70 text-center mt-1">For Institutional Traders</p>
            <div className="my-4 h-[60px] text-center">
              <p className="text-3xl font-black text-slate-100">${isAnnual ? "149" : "199"} <span className="text-sm font-normal text-slate-400">/mo</span></p>
              {isAnnual && <p className="text-[10px] text-slate-500 lowercase tracking-widest mt-1">Billed $1,788 annually</p>}
            </div>
            <ul className="space-y-3 mb-8 text-sm text-slate-300">
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-violet-400" /> Dedicated clustered IP</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-violet-400" /> Walk-forward optimization</li>
              <li className="flex gap-2 items-center"><Check className="w-4 h-4 text-violet-400" /> White-glove support</li>
            </ul>
            <button className="w-full btn-secondary text-violet-400 border-violet-500/30 hover:bg-violet-500/10 py-2" onClick={onClose}>Upgrade to Max</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const [activeAvatar, setActiveAvatar] = useState(0);
  const [theme, setTheme] = useState("system");
  const [lang, setLang] = useState("EN");
  const [showPricing, setShowPricing] = useState(false);

  const { data: sessionData } = useQuery(getAuthSessionOptions());

  // const { data: sessionData } = useQuery({
    // queryKey: ['session'],
    // queryFn: () => mockGetSession(),
  // });

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    // Explicitly disable the Sentinel bypass on sign out to prevent redirect loops
    router.push("/?bypass_auth=false");
  };

  return (
    <>
      <PricingModal isOpen={showPricing} onClose={() => setShowPricing(false)} />

      <div className="max-w-3xl mx-auto space-y-8 pb-20">
        <div className="flex flex-col md:flex-row items-center gap-6 mb-8 text-center md:text-left">
          <div className={cn("w-24 h-24 rounded-full border-4 border-slate-900 shadow-xl", NEUTRAL_AVATARS[activeAvatar])} />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">Account Settings</h1>
            <p className="text-slate-400 text-sm">Manage your account.</p>
          </div>
        </div>

        <div className="space-y-6">

          {/* Avatar Selection */}
          <div className="glass-card p-6 border-slate-800/50">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500 mb-4">Profile Identity</h2>
            <div className="flex items-center gap-4">
              {NEUTRAL_AVATARS.map((bg, idx) => (
                <button
                  key={idx}
                  onClick={() => setActiveAvatar(idx)}
                  className={cn(
                    "w-12 h-12 rounded-full cursor-pointer transition-transform hover:scale-110",
                    bg,
                    activeAvatar === idx ? "ring-2 ring-cyan-400 ring-offset-2 ring-offset-slate-950 scale-110" : "opacity-50"
                  )}
                />
              ))}
            </div>
          </div>

          {/* Preferences (Feature Flags) */}
          <div className="glass-card p-6 border-slate-800/50">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500 mb-4">Application Preferences</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

              {/* Theme Toggle */}
              <div className="space-y-3">
                <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-2"><Moon size={14} /> Appearance</label>
                <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1">
                  {["light", "dark", "system"].map(t => (
                    <button key={t} onClick={() => setTheme(t)} className={cn(
                      "flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm capitalize transition-colors",
                      theme === t ? "bg-slate-800 text-slate-100 shadow-sm" : "text-slate-500 hover:text-slate-300"
                    )}>
                      {t === "light" && <Sun size={14} />}
                      {t === "dark" && <Moon size={14} />}
                      {t === "system" && <Monitor size={14} />}
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Language Toggle */}
              <div className="space-y-3">
                <label className="text-xs font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-2"><Globe size={14} /> Language</label>
                <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1">
                  {["EN", "ES"].map(l => (
                    <button key={l} onClick={() => setLang(l)} className={cn(
                      "flex-1 py-2 rounded-md text-sm transition-colors",
                      lang === l ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 font-semibold" : "text-slate-500 hover:text-slate-300"
                    )}>
                      {l === "EN" ? "English" : "Español"}
                    </button>
                  ))}
                </div>
              </div>

            </div>
          </div>

          {/* Tier Card */}
          <div className="glass-card p-6 border-slate-800/50 relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 rounded-full blur-[80px] group-hover:bg-cyan-500/10 transition-colors pointer-events-none" />
            <div className="flex items-center justify-between relative z-10">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500 mb-1">Current Plan</h2>
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-slate-100">{sessionData?.subscription_tier === "free" ? "Developer" : sessionData?.subscription_tier}</span>
                  {sessionData?.is_admin && (
                    <span className="bg-emerald-500/10 text-emerald-400 text-[10px] px-2 py-0.5 rounded-full border border-emerald-400/20 uppercase font-bold tracking-widest">
                      System Admin
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => setShowPricing(true)} className="btn-secondary text-sm flex items-center gap-2 border-cyan-500/30 hover:bg-cyan-500/10 hover:text-cyan-400">
                <Zap size={14} className="text-cyan-400" /> Upgrade Plan
              </button>
            </div>

            <div className="mt-8 border-t border-slate-800/50 pt-6 relative z-10">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-slate-400">Execution Quota</span>
                <span className="text-slate-100 font-bold">{sessionData?.remaining_quota || 0} / 50</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-900 border border-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400"
                  style={{ width: `${Math.min(((sessionData?.remaining_quota || 0) / 50) * 100, 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Security & System */}
          <div className="glass-card p-6 border-slate-800/50">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500 mb-4">Security</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">

              <div className="border border-slate-800 rounded-xl p-4 flex flex-col gap-3 justify-center items-center bg-slate-900/50 hover:bg-slate-800/50 transition-colors cursor-pointer group">
                <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center group-hover:bg-cyan-500/20 group-hover:text-cyan-400 transition-colors">
                  <Shield className="w-5 h-5 text-slate-400 group-hover:text-cyan-400" />
                </div>
                <div className="text-center">
                  <h3 className="font-semibold text-slate-100 text-sm">Change Password</h3>
                </div>
              </div>

              <div className="border border-slate-800 rounded-xl p-4 flex flex-col gap-3 justify-center items-center bg-slate-900/50 hover:bg-slate-800/50 transition-colors cursor-pointer group">
                <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center group-hover:bg-emerald-500/20 transition-colors">
                  <Shield className="w-5 h-5 text-slate-400 group-hover:text-emerald-400" />
                </div>
                <div className="text-center">
                  <h3 className="font-semibold text-slate-100 text-sm">Enable MFA</h3>
                </div>
              </div>

              <div className="border border-slate-800 rounded-xl p-4 flex flex-col gap-3 justify-center items-center bg-slate-900/50 cursor-not-allowed opacity-50">
                <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center">
                  <User className="w-5 h-5 text-slate-400" />
                </div>
                <div className="text-center">
                  <h3 className="font-semibold text-slate-100 text-sm">SSO Connected</h3>
                </div>
              </div>

              <div
                onClick={handleSignOut}
                className="border border-slate-800 rounded-xl p-4 flex flex-col gap-3 justify-center items-center bg-slate-900/50 hover:border-red-500/30 hover:bg-red-500/10 transition-colors cursor-pointer group"
              >
                <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center group-hover:bg-red-500/20 transition-colors">
                  <LogOut className="w-5 h-5 text-red-500" />
                </div>
                <div className="text-center">
                  <h3 className="font-semibold text-red-400 text-sm">Sign Out</h3>
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>
    </>
  );
}
