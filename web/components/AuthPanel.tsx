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
          router.push("/dashboard");
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
          router.push("/dashboard");
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
        options: { redirectTo: `${window.location.origin}/dashboard` }
      });
      if (socialError) throw socialError;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Social auth failed");
    }
  };

  if (!mounted) return <div className="h-[400px] flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;

  return (
    <div
      id="auth-panel"
      ref={panelRef}
      className={`relative group perspective-1000 transition-all duration-700 ${isHighlighted ? 'scale-[1.02]' : ''}`}
    >
      <div className={`absolute inset-0 bg-primary/20 blur-[100px] rounded-full group-hover:bg-primary/30 transition-all duration-700 pointer-events-none ${isHighlighted ? 'bg-primary/50 blur-[120px]' : ''}`}></div>

      <div className={`glass-panel relative z-10 rounded-2xl border transition-all duration-500 p-8 shadow-2xl ${isHighlighted ? 'border-primary shadow-[0_0_50px_rgba(153,247,255,0.2)]' : 'border-outline-variant/30'}`}>
        <div className="flex justify-center items-center mb-8">
          <h2 className="text-2xl font-headline font-black uppercase tracking-tighter text-gradient-cyan">
            {resetSent ? "RECOVERY" : authMode === "login" ? "WELCOME BACK" : authMode === "signup" ? "GET STARTED" : "RECOVERY"}
          </h2>
        </div>

        {resetSent ? (
          <div className="py-8 text-center space-y-4 animate-in fade-in zoom-in duration-500">
            <CheckCircle2 className="w-12 h-12 text-success mx-auto" strokeWidth={1.5} />
            <h3 className="text-lg font-bold text-on-surface uppercase tracking-tight">Email Dispatched</h3>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              We&apos;ve sent a recovery link to <span className="text-primary font-bold">{email}</span>.
            </p>
            <button
              onClick={() => { setAuthMode("login"); setResetSent(false); }}
              className="text-[10px] text-primary hover:underline uppercase tracking-widest font-bold pt-4"
            >
              Return to Sign In
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {error && (
              <div className="mb-6 p-4 bg-error/10 border border-error/20 rounded-xl flex items-start gap-3 text-error text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary outline-none"
                  placeholder="operator@argus.io"
                  required
                />
              </div>

              {authMode !== "forgot_password" && (
                <>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Password</label>
                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary outline-none pr-12"
                        placeholder="••••••••••••"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-on-surface-variant hover:text-on-surface transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {authMode === "signup" && (
                     <div className="space-y-1">
                       <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Confirm Password</label>
                       <input
                         type={showPassword ? "text" : "password"}
                         value={confirmPassword}
                         onChange={(e) => setConfirmPassword(e.target.value)}
                         className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary outline-none"
                         placeholder="••••••••••••"
                         required
                       />
                     </div>
                  )}
                </>
              )}

              {authMode === "login" && (
                 <div className="flex justify-end">
                   <button type="button" onClick={() => setAuthMode("forgot_password")} className="text-[10px] text-primary hover:text-primary-dim uppercase tracking-widest font-bold">Forgot Password?</button>
                 </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 mt-4 bg-primary text-on-primary rounded-xl text-xs font-bold uppercase tracking-widest transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
              >
                {loading ? "PROCESSING..." : authMode === "login" ? "SIGN IN TO TERMINAL" : authMode === "signup" ? "CREATE FREE ACCOUNT" : "SEND RECOVERY LINK"}
              </button>
            </form>

            {Features.SOCIAL_AUTH && authMode !== "forgot_password" && (
              <>
                <div className="my-6 flex items-center gap-4">
                  <div className="flex-1 h-px bg-outline-variant/20"></div>
                  <span className="text-[10px] lowercase tracking-widest text-on-surface-variant">or continue with</span>
                  <div className="flex-1 h-px bg-outline-variant/20"></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => handleSocialAuth('google')} className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-white hover:border-white transition-all flex justify-center group rounded-xl">
                    <GoogleIcon className="w-5 h-5" />
                  </button>
                  <button onClick={() => handleSocialAuth('discord')} className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-[#5865F2] hover:border-[#5865F2] hover:text-white transition-all flex justify-center group rounded-xl">
                    <DiscordIcon className="w-5 h-5 text-[#5865F2] group-hover:text-white" />
                  </button>
                </div>
              </>
            )}

            <div className="mt-8 text-center">
              <button
                onClick={() => { setAuthMode(authMode === "login" ? "signup" : "login"); setError(null); }}
                className="text-[10px] text-on-surface-variant hover:text-primary uppercase tracking-[0.2em] font-bold transition-colors"
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
