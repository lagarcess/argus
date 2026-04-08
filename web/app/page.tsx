"use client";

// Skip static generation for this auth page
export const dynamic = "force-dynamic";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { GoogleIcon, DiscordIcon } from "@/components/Icons";
import { TopNav } from "@/components/TopNav";
import { Eye, EyeOff, Zap, AlertCircle, CheckCircle2 } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/components/AuthContext";

export default function LandingPage() {
  const [authMode, setAuthMode] = useState<"login" | "signup" | "forgot_password">("signup");
  const [resetSent, setResetSent] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isHighlighted, setIsHighlighted] = useState(false);
  const authPanelRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { login } = useAuth();

  // Handle hash-based navigation for mode switching
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash;
      if (hash === "#auth-panel" || hash === "#login") {
        setAuthMode("login");
        scrollToAuth();
      } else if (hash === "#signup") {
        setAuthMode("signup");
        scrollToAuth();
      }
    };

    handleHash();
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  const scrollToAuth = (mode?: "login" | "signup") => {
    if (mode) setAuthMode(mode);
    
    // Smooth scroll to the panel
    authPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    
    // Trigger highlight effect
    setIsHighlighted(true);
    setTimeout(() => setIsHighlighted(false), 2000);
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (authMode === "signup") {
        const { data, error: signupError } = await supabase.auth.signUp({
          email,
          password,
        });
        if (signupError) throw signupError;
        if (data.session) {
          login(data.session.access_token, data.session.user.email || email);
          router.push("/dashboard");
        } else {
          setError("Verification email sent. Please check your inbox.");
        }
      } else {
        const { data, error: loginError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (loginError) throw loginError;
        if (data.session) {
          login(data.session.access_token, data.session.user.email || email);
          router.push("/dashboard");
        }
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An error occurred during authentication.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });

      if (resetError) throw resetError;

      setResetSent(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to send reset email.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSocialAuth = async (provider: 'google' | 'discord') => {
    setError(null);
    try {
      const { error: socialError } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: `${window.location.origin}/dashboard`
        }
      });
      if (socialError) throw socialError;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Social authentication failed.";
      setError(message);
    }
  };

  return (
    <div className="bg-background text-on-background font-body selection:bg-primary/30 min-h-screen flex flex-col">
      <TopNav onSignInClick={() => scrollToAuth("login")} />

      <main className="flex-1 pt-32 pb-12 px-6 lg:px-12 max-w-[1600px] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24 items-center">
        {/* Left Column: Value Prop */}
        <div className="space-y-8">
          <div>
            <h1 className="text-5xl lg:text-7xl font-headline font-black tracking-tighter uppercase leading-[0.9] text-on-surface">
              SIMULATE YOUR IDEAS. <span className="text-gradient-cyan">VALIDATE YOUR EDGE.</span>
            </h1>
            <p className="mt-6 text-on-surface-variant max-w-lg text-sm md:text-base leading-relaxed">
              Argus provides high-performance pattern recognition and battle-tested simulation protocols.
              Validate your strategies against real-world friction—slippage and fees—within the high-performance Argus environment.
            </p>
            <button
              onClick={() => scrollToAuth("signup")}
              className="mt-8 px-8 py-4 rounded-xl bg-primary text-on-primary text-sm font-bold uppercase tracking-widest hover:scale-105 transition-all shadow-[0_0_30px_rgba(153,247,255,0.3)] flex items-center justify-center gap-3"
            >
              RUN YOUR FIRST SIMULATION
              <Zap className="w-4 h-4 fill-current" />
            </button>
          </div>

          {/* Social Proof / Metrics */}
          <div className="flex gap-8 pt-8 border-t border-neutral-800/50">
            <div>
              <div className="text-3xl font-headline font-black text-on-surface">14.2B</div>
              <div className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
                Strategies Tested
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

        <div 
          id="auth-panel" 
          ref={authPanelRef}
          className={`relative group perspective-1000 transition-all duration-700 ${isHighlighted ? 'scale-[1.02]' : ''}`}
        >
          <div className={`absolute inset-0 bg-primary/20 blur-[100px] rounded-full group-hover:bg-primary/30 transition-all duration-700 pointer-events-none ${isHighlighted ? 'bg-primary/50 blur-[120px]' : ''}`}></div>

          <div className={`glass-panel relative z-10 rounded-2xl border transition-all duration-500 p-8 shadow-2xl ${isHighlighted ? 'border-primary shadow-[0_0_50px_rgba(153,247,255,0.2)]' : 'border-outline-variant/30'}`}>
            <div className="flex justify-center items-center mb-8">
              <h2 className="text-2xl font-headline font-black uppercase tracking-tighter text-gradient-cyan">
                {authMode === "login" ? "WELCOME BACK" : authMode === "signup" ? "GET STARTED" : "RECOVERY"}
              </h2>
            </div>

            {resetSent ? (
              <div className="py-8 text-center space-y-4 animate-in fade-in zoom-in duration-500">
                <CheckCircle2 className="w-12 h-12 text-success mx-auto" strokeWidth={1.5} />
                <h3 className="text-lg font-bold text-on-surface uppercase tracking-tight">Email Dispatched</h3>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  We've sent a recovery link to <span className="text-primary font-bold">{email}</span>. 
                  Check your inbox to finalize your credentials.
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
                  <div className="mb-6 p-4 bg-error/10 border border-error/20 rounded-xl flex items-start gap-3 text-error text-xs animate-in slide-in-from-top-1">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <p>{error}</p>
                  </div>
                )}
                <form onSubmit={authMode === "forgot_password" ? handleForgotPassword : handleLoginSubmit} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary transition-all outline-none"
                    placeholder="operator@argus.io"
                    required
                  />
                </div>

                {authMode !== "forgot_password" && (
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                      PASSWORD
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary transition-all outline-none pr-12"
                        placeholder="••••••••••••"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-on-surface-variant hover:text-on-surface transition-colors focus:outline-none"
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {authMode === "login" && (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => setAuthMode("forgot_password")}
                      className="text-[10px] text-primary hover:text-primary-dim uppercase tracking-widest font-bold"
                    >
                      Forgot Password?
                    </button>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3.5 mt-4 bg-surface-container-highest border border-outline-variant hover:bg-primary hover:text-on-primary hover:border-primary rounded-xl text-xs font-bold uppercase tracking-widest transition-all shadow-lg flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "PROCESSING..." : (
                    authMode === "login" ? "SIGN IN TO TERMINAL" : 
                    authMode === "signup" ? "CREATE FREE ACCOUNT" : "SEND RECOVERY LINK"
                  )}
                </button>
              </form>
            </div>
          )}

            <div className="my-6 flex items-center gap-4">
              <div className="flex-1 h-px bg-outline-variant/20"></div>
              <span className="text-[10px] lowercase tracking-widest text-on-surface-variant">
                {authMode === "signup" ? "sign up with" : "log in with"}
              </span>
              <div className="flex-1 h-px bg-outline-variant/20"></div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleSocialAuth('google')}
                className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-white hover:border-white group rounded-xl transition-all flex items-center justify-center"
              >
                <GoogleIcon className="w-5 h-5 flex-shrink-0" />
              </button>
              <button
                onClick={() => handleSocialAuth('discord')}
                className="py-3 bg-surface-container-low border border-outline-variant/30 hover:bg-[#5865F2] hover:border-[#5865F2] hover:text-white rounded-xl transition-all flex items-center justify-center group"
              >
                <DiscordIcon className="w-5 h-5 text-[#5865F2] group-hover:text-white" />
              </button>
            </div>

            <div className="mt-8 text-center">
              <button
                onClick={() => setAuthMode(authMode === "login" ? "signup" : "login")}
                className="text-[10px] text-on-surface-variant hover:text-primary uppercase tracking-[0.2em] font-bold transition-colors"
                type="button"
              >
                {authMode === "login" ? "Don't have an account? Sign up" : "Already have an account? Log in"}
              </button>
            </div>
            <p className="mt-6 text-center text-[10px] text-on-surface-variant font-label opacity-70">
              By connecting, you agree to our{" "}
              <a href="#" className="underline">Terms</a> and{" "}
              <a href="#" className="underline">Privacy Policy</a>.
            </p>
          </div>
        </div>
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
