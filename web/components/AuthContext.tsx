"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import { User } from "@supabase/supabase-js";
import { isDevelopmentEnv } from "@/lib/app-env";
import { postAuthLogout } from "@/lib/api/sdk.gen";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 1. Initial session check
    const initAuth = async () => {
      const searchParams = new URLSearchParams(window.location.search);
      const bypassParam = searchParams.get("bypass_auth");
      const hasBypassParam = bypassParam === "true";
      const isExplicitDisable = bypassParam === "false";
      const hasBypassCookie = typeof document !== "undefined" && document.cookie.includes("sb-mock-bypass=true");

      const isMock = !isExplicitDisable && (process.env.NEXT_PUBLIC_MOCK_AUTH === "true" || (isDevelopmentEnv() && (hasBypassParam || hasBypassCookie)));

      if (isMock) {
        console.log("🛡️ Mock Auth Active: Bypassing Supabase");
        setUser({
          id: "mock-dev-id",
          email: "mock@argus.ai",
          user_metadata: { full_name: "Mock Developer" },
          app_metadata: { provider: "email" },
          aud: "authenticated",
          role: "authenticated",
          created_at: new Date().toISOString(),
        } as User);
        setToken("mock-access-token");
        setLoading(false);
        return;
      }

      if (isExplicitDisable) {
        setUser(null);
        setToken(null);
        // Supabase session should also be cleared just in case
        await supabase.auth.signOut();
      }

      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        setUser(session.user);
        setToken(session.access_token);
      }
      setLoading(false);
    };

    initAuth();

    // 2. Listen for auth changes (SSO, Logout, Session refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      const searchParams = new URLSearchParams(window.location.search);
      const hasBypassCookie = typeof document !== "undefined" && document.cookie.includes("sb-mock-bypass=true");
      const isMock = process.env.NEXT_PUBLIC_MOCK_AUTH === "true" || (isDevelopmentEnv() && (searchParams.get("bypass_auth") === "true" || hasBypassCookie));
      if (isMock) return;

      if (session) {
        setUser(session.user);
        setToken(session.access_token);
      } else {
        setUser(null);
        setToken(null);
      }
      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const logout = async () => {
    try {
      await postAuthLogout();
    } catch {
      // noop: local session still must be cleared
    }
    await supabase.auth.signOut();
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
