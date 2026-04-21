"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TopNav } from "@/components/TopNav";
import { Eye, EyeOff, Lock, AlertCircle, CheckCircle2 } from "lucide-react";
import { supabase } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const router = useRouter();

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);

    try {
      const { error: resetError } = await supabase.auth.updateUser({
        password: password,
      });

      if (resetError) throw resetError;

      setSuccess(true);
      setTimeout(() => {
        router.push("/");
      }, 3000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An error occurred while resetting your password.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-background text-on-background font-body selection:bg-primary/30 min-h-screen flex flex-col">
      <TopNav />

      <main className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md relative group perspective-1000">
          <div className="absolute inset-0 bg-primary/10 blur-[80px] rounded-full group-hover:bg-primary/20 transition-colors duration-700 pointer-events-none"></div>

          <div className="glass-panel relative z-10 rounded-2xl border border-outline-variant/30 p-8 shadow-2xl">
            <div className="flex justify-center items-center mb-8">
              <h2 className="text-2xl font-headline font-black uppercase tracking-tighter text-gradient-cyan text-center">
                RESET YOUR PASSWORD
              </h2>
            </div>

            {success ? (
              <div className="space-y-6 text-center animate-in fade-in zoom-in duration-500">
                <div className="flex justify-center">
                  <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center">
                    <CheckCircle2 className="w-8 h-8 text-success" />
                  </div>
                </div>
                <div>
                  <h3 className="text-lg font-bold text-on-surface">Password Updated</h3>
                  <p className="text-sm text-on-surface-variant mt-2">
                    Your password has been successfully reset. Redirecting you to login...
                  </p>
                </div>
              </div>
            ) : (
              <form onSubmit={handleResetSubmit} className="space-y-4">
                {error && (
                  <div className="p-4 bg-error/10 border border-error/20 rounded-xl flex items-start gap-3 text-error text-xs">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <p>{error}</p>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                    NEW PASSWORD
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
                    >
                      {showPassword ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">
                    CONFIRM NEW PASSWORD
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary transition-all outline-none"
                    placeholder="••••••••••••"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-4 mt-6 bg-primary text-on-primary rounded-xl text-xs font-bold uppercase tracking-widest transition-all shadow-lg flex items-center justify-center gap-2 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
                >
                  {loading ? "UPDATING..." : (
                    <>
                      UPDATE PASSWORD
                      <Lock className="w-3 h-3" />
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      </main>

      <footer className="px-6 py-8 border-t border-neutral-800/50 text-[10px] tracking-wider uppercase opacity-50 text-center">
        © 2026 ARGUS QUANTITATIVE. ALL RIGHTS RESERVED.
      </footer>
    </div>
  );
}
