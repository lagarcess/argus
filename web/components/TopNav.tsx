"use client";

import Link from "next/link";
import { useTheme } from "./ThemeProvider";

export function TopNav() {
  const { theme, setTheme } = useTheme();

  return (
    <nav className="fixed top-0 w-full z-50 flex justify-between items-center px-6 py-3 bg-neutral-950/40 backdrop-blur-xl border-b border-neutral-800/50 shadow-[0_20px_40px_rgba(0,0,0,0.4)] md:pl-72">
      {/* Mobile only title, on desktop it's in the sidebar */}
      <div className="flex items-center gap-8 md:hidden">
        <span className="text-2xl font-bold tracking-tighter text-cyan-400 font-headline">ARGUS</span>
      </div>

      <div className="hidden md:flex items-center gap-6 text-sm font-headline tracking-tight">
        <Link href="#" className="text-neutral-400 hover:text-cyan-300 transition-colors duration-200">Markets</Link>
        <Link href="#" className="text-neutral-400 hover:text-cyan-300 transition-colors duration-200">Terminal</Link>
        <Link href="#" className="text-neutral-400 hover:text-cyan-300 transition-colors duration-200">API</Link>
      </div>

      <div className="flex items-center gap-4 ml-auto">
        <div className="flex items-center gap-3 px-3 py-1 bg-surface-container rounded-full border border-outline-variant/20 hidden sm:flex">
          <span className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Simulations: 14/100</span>
          <div className="h-1 w-12 bg-surface-variant rounded-full overflow-hidden">
            <div className="h-full bg-primary w-[14%]"></div>
          </div>
        </div>

        <span className="hidden lg:block text-[10px] font-bold text-primary uppercase tracking-[0.2em] border border-primary/30 px-2 py-0.5 rounded">Pro Member</span>

        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-neutral-400 hover:text-cyan-300 cursor-pointer hidden sm:block">language</span>
          <Link href="/settings">
            <span className="material-symbols-outlined text-neutral-400 hover:text-cyan-300 cursor-pointer">settings</span>
          </Link>
          <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            <span className="material-symbols-outlined text-neutral-400 hover:text-cyan-300 cursor-pointer">
              {theme === "dark" ? "light_mode" : "dark_mode"}
            </span>
          </button>
        </div>

        <div className="w-8 h-8 rounded-full border border-primary/20 bg-surface-variant flex items-center justify-center overflow-hidden">
             <span className="material-symbols-outlined text-sm text-primary">person</span>
        </div>
      </div>
    </nav>
  );
}
