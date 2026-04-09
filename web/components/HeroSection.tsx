"use client";

import { Zap } from "lucide-react";
import { MetricCard } from "./MetricCard";

interface HeroSectionProps {
  onActionClick: () => void;
}

export function HeroSection({ onActionClick }: HeroSectionProps) {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-left-4 duration-700">
      <div>
        <h1 className="text-5xl lg:text-7xl font-headline font-black tracking-tighter uppercase leading-[0.9] text-on-surface">
          SIMULATE YOUR IDEAS. <span className="text-gradient-cyan">VALIDATE YOUR EDGE.</span>
        </h1>
        <p className="mt-6 text-on-surface-variant max-w-lg text-sm md:text-base leading-relaxed">
          Argus provides high-performance pattern recognition and battle-tested simulation protocols.
          Validate your strategies against real-world friction—slippage and fees—within the high-performance Argus environment.
        </p>
        <button
          onClick={onActionClick}
          className="mt-8 px-8 py-4 rounded-xl bg-primary text-on-primary text-sm font-bold uppercase tracking-widest hover:scale-105 active:scale-95 transition-all shadow-[0_0_30px_rgba(153,247,255,0.3)] flex items-center justify-center gap-3"
        >
          RUN YOUR FIRST SIMULATION
          <Zap className="w-4 h-4 fill-current" />
        </button>
      </div>

      {/* Social Proof / Metrics */}
      <div className="flex gap-8 pt-8 border-t border-neutral-800/50">
        <MetricCard value="14.2B" label="Strategies Tested" />
        <MetricCard value="0.1ms" label="Simulation Latency" />
        <MetricCard value="99.9%" label="Market Accuracy" className="hidden md:block" />
      </div>
    </div>
  );
}
