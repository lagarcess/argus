"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthContext";
import { LogOut } from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: "/dashboard", icon: "dashboard", label: "Dashboard" },
    { href: "/builder", icon: "add_circle", label: "New Strategy" },
    { href: "/history", icon: "history", label: "History" },
    { href: "/settings", icon: "settings", label: "Settings" },
  ];

  const { logout } = useAuth();
  const router = useRouter();

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-neutral-950 border-r border-neutral-800/30 flex-col py-8 z-40 hidden md:flex">
      <div className="px-8 mb-12 mt-8">
        <div className="text-xl font-black text-cyan-400 font-headline tracking-tighter">ARGUS</div>
        <div className="text-[10px] text-neutral-500 uppercase tracking-[0.3em] font-headline">
          Argus Observatory
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

      <div className="mt-auto px-6 space-y-3">
        <button
          onClick={async () => {
            await logout();
            router.push("/");
          }}
          className="w-full flex items-center gap-4 px-4 py-3 rounded-xl font-headline text-sm uppercase tracking-widest text-neutral-500 hover:text-error hover:bg-error/5 transition-all duration-300 group"
        >
          <LogOut className="w-5 h-5 group-hover:text-error" />
          Log Out
        </button>

        <Link href="/builder" className="w-full h-12 flex items-center justify-center bg-cyan-400 text-neutral-950 font-black text-[10px] tracking-widest uppercase rounded-xl shadow-[0_0_20px_rgba(34,211,238,0.2)] hover:scale-[1.02] active:scale-[0.98] transition-transform">
          Execute Backtest
        </Link>
      </div>
    </aside>
  );
}
