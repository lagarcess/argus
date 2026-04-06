"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

interface AuthContextType {
  user: { email: string } | null;
  token: string | null;
  loading: boolean;
  login: (token: string, email: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<{ email: string } | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem("auth_token");
    const savedEmail = localStorage.getItem("auth_email");
    if (savedToken && savedEmail) {
      setToken(savedToken);
      setUser({ email: savedEmail });
    }
    setLoading(false);
  }, []);

  const login = (newToken: string, email: string) => {
    localStorage.setItem("auth_token", newToken);
    localStorage.setItem("auth_email", email);
    setToken(newToken);
    setUser({ email });
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_email");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
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
