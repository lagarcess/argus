"use client";

import { useEffect, useState, useImperativeHandle, forwardRef, useRef } from "react";
import { useRouter } from "next/navigation";
import { GoogleIcon, DiscordIcon } from "@/components/Icons";
import { Eye, EyeOff, AlertCircle, CheckCircle2 } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { Features } from "@/lib/features";

export interface AuthPanelHandle {
  setMode: (mode: "login" | "signup" | "forgot_password") => void;
  scrollIntoView: () => void;
}

export const AuthPanel = forwardRef<AuthPanelHandle>((_, ref) => {
  const [authMode, setAuthMode] = useState<"login" | "signup" | "forgot_password">("signup");
  const [resetSent, setResetSent] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isHighlighted, setIsHighlighted] = useState(false);
  const [mounted, setMounted] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
  }, []);

  useImperativeHandle(ref, () => ({
    setMode: (mode) => {
      setAuthMode(mode);
      setError(null);
    },
    scrollIntoView: () => {
      panelRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      setIsHighlighted(true);
      setTimeout(() => setIsHighlighted(false), 2000);
    }
  }));

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (authMode === "signup") {
        if (password !== confirmPassword) {
          throw new Error("Passwords do not match.");
        }
        const { data, error: signupError } = await supabase.auth.signUp({
          email,
          password,
        });
        if (signupError) throw signupError;
        if (data.session) {
          router.push("/builder");
        } else {
          setError("Verification email sent. Please check your inbox.");
        }
      } else if (authMode === "login") {
        const { data, error: loginError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (loginError) throw loginError;
        if (data.session) {
          router.push("/builder");
        }
      } else {
        // Forgot Password
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        });
        if (resetError) throw resetError;
        setResetSent(true);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSocialAuth = async (provider: 'google' | 'discord') => {
    setError(null);
    try {
      const { error: socialError } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: `${window.location.origin}/builder` }
      });
      if (socialError) throw socialError;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Social auth failed");
    }
  };

  if (!mounted) return <div className="h-[400px] flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400"></div></div>;

  return (
    <div
      id="auth-panel"
      ref={panelRef}
      className={`relative group transition-all duration-700 ${isHighlighted ? 'scale-[1.02]' : ''}`}
    >
      <div className={`absolute inset-0 bg-cyan-400/10 blur-[100px] rounded-full group-hover:bg-cyan-400/20 transition-all duration-700 pointer-events-none ${isHighlighted ? 'bg-cyan-400/30 blur-[120px]' : ''}`}></div>

      <div className={`glass-card relative z-10 border transition-all duration-500 p-8 shadow-2xl ${isHighlighted ? 'border-cyan-400 shadow-[0_0_50px_rgba(0,240,255,0.2)]' : 'border-slate-800/50'}`}>
        <div className="flex justify-center items-center mb-8">
          <h2 className="text-2xl font-black uppercase tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-emerald-400">
            {resetSent ? "RECOVERY" : authMode === "login" ? "WELCOME BACK" : authMode === "signup" ? "GET STARTED" : "RECOVERY"}
          </h2>
        </div>

        {resetSent ? (
          <div className="py-8 text-center space-y-4 animate-in fade-in zoom-in duration-500">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" strokeWidth={1.5} />
            <h3 className="text-lg font-bold text-slate-100 uppercase tracking-tight">Email Dispatched</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              We&apos;ve sent a recovery link to <span className="text-cyan-400 font-bold">{email}</span>.
            </p>
            <button
              onClick={() => { setAuthMode("login"); setResetSent(false); }}
              className="text-[10px] text-cyan-400 hover:text-cyan-300 hover:underline uppercase tracking-widest font-bold pt-4"
            >
              Return to Sign In
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {error && (
              <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400 text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm text-slate-100 focus:ring-1 focus:ring-cyan-400 outline-none"
                  placeholder="operator@argus.io"
                  required
                />
              </div>

              {authMode !== "forgot_password" && (
                <>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Password</label>
                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm text-slate-100 focus:ring-1 focus:ring-cyan-400 outline-none pr-12"
                        placeholder="••••••••••••"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-slate-400 hover:text-slate-100 transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {authMode === "signup" && (
                     <div className="space-y-1">
                       <label className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Confirm Password</label>
                       <input
                         type={showPassword ? "text" : "password"}
                         value={confirmPassword}
                         onChange={(e) => setConfirmPassword(e.target.value)}
                         className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-sm text-slate-100 focus:ring-1 focus:ring-cyan-400 outline-none"
                         placeholder="••••••••••••"
                         required
                       />
                     </div>
                  )}
                </>
              )}

              {authMode === "login" && (
                 <div className="flex justify-end">
                   <button type="button" onClick={() => setAuthMode("forgot_password")} className="text-[10px] text-cyan-400 hover:text-cyan-300 uppercase tracking-widest font-bold">Forgot Password?</button>
                 </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full btn-primary py-3.5 mt-4 text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-50"
              >
                {loading ? "PROCESSING..." : authMode === "login" ? "SIGN IN TO TERMINAL" : authMode === "signup" ? "CREATE FREE ACCOUNT" : "SEND RECOVERY LINK"}
              </button>

              {authMode === "login" && (
                <p className="text-[9px] text-center text-slate-500 mt-3 font-medium px-4">
                  By using our services you agree to our <a href="#" className="underline hover:text-cyan-400">Terms of Service</a> and <a href="#" className="underline hover:text-cyan-400">Privacy Policy</a>
                </p>
              )}
            </form>

            {authMode !== "forgot_password" && (
              <>
                <div className="my-6 flex items-center gap-4">
                  <div className="flex-1 h-px bg-slate-800"></div>
                  <span className="text-[10px] lowercase tracking-widest text-slate-500">or continue with</span>
                  <div className="flex-1 h-px bg-slate-800"></div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => handleSocialAuth('google')} className="py-3 bg-slate-900 border border-slate-800 hover:bg-white hover:border-white hover:text-slate-950 transition-all flex justify-center group rounded-xl">
                    <GoogleIcon className="w-5 h-5 flex-shrink-0" />
                  </button>
                  <button onClick={() => handleSocialAuth('discord')} className="py-3 bg-slate-900 border border-slate-800 hover:bg-[#5865F2] hover:border-[#5865F2] text-[#5865F2] hover:text-white transition-all flex justify-center group rounded-xl">
                    <DiscordIcon className="w-5 h-5 flex-shrink-0" />
                  </button>
                </div>
              </>
            )}

            <div className="mt-8 text-center border-t border-slate-800 pt-6">
              <button
                onClick={() => { setAuthMode(authMode === "login" ? "signup" : "login"); setError(null); }}
                className="text-[10px] text-slate-400 hover:text-cyan-400 uppercase tracking-widest font-bold transition-colors"
                style={{ letterSpacing: '0.2em' }}
              >
                {authMode === "login" ? "Don't have an account? Sign up" : "Already have an account? Log in"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

AuthPanel.displayName = "AuthPanel";
