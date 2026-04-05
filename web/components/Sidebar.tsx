"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: "/dashboard", icon: "dashboard", label: "Dashboard" },
    { href: "/builder", icon: "add_circle", label: "New Strategy" },
    { href: "/history", icon: "history", label: "History" },
    { href: "/settings", icon: "settings", label: "Settings" },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-neutral-950 border-r border-neutral-800/30 flex-col py-8 z-40 hidden md:flex">
      <div className="px-8 mb-12 mt-8">
        <div className="text-xl font-black text-cyan-400 font-headline tracking-tighter">ARGUS</div>
        <div className="text-[10px] text-neutral-500 uppercase tracking-[0.3em] font-headline">
          Obsidian Observatory
        </div>
      </div>

      <div className="flex flex-col gap-1 px-4 flex-1">
        {links.map((link) => {
          const isActive = pathname === link.href || pathname.startsWith(link.href + "/");
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-4 px-4 py-3 rounded-xl font-headline text-sm uppercase tracking-widest transition-all duration-300 ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-400 border-r-2 border-cyan-400"
                  : "text-neutral-500 hover:text-neutral-200 hover:bg-neutral-900"
              }`}
            >
              <span className="material-symbols-outlined" style={isActive ? { fontVariationSettings: "'FILL' 1" } : {}}>
                {link.icon}
              </span>
              {link.label}
            </Link>
          );
        })}
      </div>

      <div className="mt-auto px-6">
        <Link href="/builder" className="w-full flex items-center justify-center bg-primary text-on-primary-container font-black text-[10px] tracking-widest uppercase py-4 rounded-xl shadow-[0_0_20px_rgba(153,247,255,0.2)] hover:scale-[1.02] active:scale-[0.98] transition-transform">
          Execute Backtest
        </Link>
      </div>
    </aside>
  );
}
