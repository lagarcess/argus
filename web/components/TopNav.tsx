"use client";

import { useEffect, useState } from "react";
import Link from "next/navigation";
import { useAuth } from "./AuthContext";
import { User, Settings } from "lucide-react";

export function TopNav() {
  const { user, token } = useAuth();
  const [usage, setUsage] = useState<{ count: number, limit: number | null, tier: string } | null>(null);

  useEffect(() => {
    if (user && token) {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      fetch(`${apiUrl}/api/v1/usage`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch usage");
        return res.json();
      })
      .then(data => setUsage(data))
      .catch(err => console.error("Usage fetch error:", err));
    }
  }, [user, token]);

  return (
    <nav className="fixed top-0 w-full z-50 flex justify-between items-center px-6 py-4 bg-neutral-950/40 backdrop-blur-xl border-b border-neutral-800/50 shadow-[0_20px_40px_rgba(0,0,0,0.4)]">
      <div className="flex items-center gap-3">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <span className="text-2xl font-black tracking-tighter text-cyan-400 font-headline leading-none">ARGUS</span>
        </Link>
        <span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest bg-amber-500/10 text-amber-500 border border-amber-500/20 leading-none">
          V0.1 - PUBLIC BETA
        </span>
      </div>

      <div className="flex items-center gap-6 ml-auto">
        {user && usage && usage.limit !== null && (
          <div className="flex items-center gap-3 px-3 py-1.5 bg-neutral-900/50 rounded-full border border-neutral-800 hidden sm:flex">
            <span className="text-[10px] uppercase tracking-widest text-neutral-400 font-bold">
              Simulations: {usage.count}/{usage.limit}
            </span>
            <div className="h-1 w-12 bg-neutral-800 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-1000 ${usage.count >= usage.limit ? 'bg-red-500' : 'bg-cyan-400'}`}
                style={{ width: `${Math.min((usage.count / usage.limit) * 100, 100)}%` }}
              ></div>
            </div>
          </div>
        )}

        {user && usage?.tier === "pro" && (
          <span className="hidden lg:block text-[10px] font-bold text-cyan-400 uppercase tracking-[0.2em] border border-cyan-400/30 px-2 py-0.5 rounded">
            Pro Member
          </span>
        )}

        {user ? (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Link href="/settings">
                <Settings className="w-4 h-4 text-neutral-400 hover:text-cyan-400 cursor-pointer transition-colors" />
              </Link>
            </div>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-neutral-900 border border-neutral-800 hover:border-cyan-400/50 transition-all text-xs font-bold uppercase tracking-widest"
            >
              <User className="w-4 h-4 text-cyan-400" />
              <span className="text-neutral-200">Dashboard</span>
            </Link>
          </div>
        ) : (
          <Link
            href="/#auth-panel"
            className="h-11 px-8 rounded-full bg-cyan-400 text-neutral-950 text-xs font-bold uppercase tracking-widest hover:bg-cyan-300 transition-all shadow-[0_0_20px_rgba(34,211,238,0.3)] flex items-center justify-center font-bold"
          >
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}
