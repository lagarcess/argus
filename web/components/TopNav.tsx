"use client";

export function TopNav() {

  return (
    <nav className="fixed top-0 w-full z-50 flex justify-between items-center px-6 py-4 bg-neutral-950/40 backdrop-blur-xl border-b border-neutral-800/50 shadow-[0_20px_40px_rgba(0,0,0,0.4)]">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-black tracking-tighter text-cyan-400 font-headline leading-none">ARGUS</span>
        <span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest bg-amber-500/10 text-amber-500 border border-amber-500/20 leading-none">
          V0.1 - PUBLIC BETA
        </span>
      </div>

      <div className="flex items-center gap-6 ml-auto">

        <button className="h-11 px-8 rounded-full bg-cyan-400 text-neutral-950 text-xs font-bold uppercase tracking-widest hover:bg-cyan-300 transition-all shadow-[0_0_20px_rgba(34,211,238,0.3)] flex items-center justify-center">
          Sign In
        </button>
      </div>
    </nav>
  );
}
