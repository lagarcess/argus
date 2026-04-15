"use client";

import React, { useState, useRef } from "react";
import { motion, AnimatePresence, useMotionValue, useSpring } from "framer-motion";
import { Lightning, Sparkle, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface CoDrafterBarProps {
  onDraft: (prompt: string) => void;
  isDrafting: boolean;
  quotaRemaining: number;
}

export function CoDrafterBar({ onDraft, isDrafting, quotaRemaining }: CoDrafterBarProps) {
  const [prompt, setPrompt] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  // Magnetic Pull Physics
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springConfig = { damping: 25, stiffness: 400 };
  const magneticX = useSpring(mouseX, springConfig);
  const magneticY = useSpring(mouseY, springConfig);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // Calculate distance from center
    const deltaX = e.clientX - centerX;
    const deltaY = e.clientY - centerY;

    // Only apply magnetic pull when very close or hovering
    if (Math.abs(deltaX) < rect.width && Math.abs(deltaY) < rect.height * 2) {
      mouseX.set(deltaX * 0.1); // 10% pull
      mouseY.set(deltaY * 0.2); // 20% pull
    } else {
      mouseX.set(0);
      mouseY.set(0);
    }
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !isDrafting && quotaRemaining > 0) {
      onDraft(prompt);
      setPrompt("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 w-[95%] sm:w-auto"
    >
      <motion.div
        ref={containerRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{ x: magneticX, y: magneticY }}
        className={cn(
          "relative flex items-center p-2 pl-6 pr-2 max-w-2xl w-full sm:w-[600px] mx-auto",
          "rounded-[2.5rem] bg-[#131313]/80 backdrop-blur-xl border border-white/10",
          "shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-colors duration-500",
          isFocused ? "border-[#00f1fe]/30" : "hover:border-white/20"
        )}
      >
        {/* Iridescent Pulse for Drafting State */}
        <AnimatePresence>
          {isDrafting && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: [0.4, 0.8, 0.4] }}
              exit={{ opacity: 0 }}
              transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
              className="absolute inset-0 rounded-[2.5rem] pointer-events-none -z-10 bg-[linear-gradient(135deg,rgba(34,211,238,0.18)_0%,rgba(16,185,129,0.18)_50%,rgba(34,211,238,0.18)_100%)] bg-[length:200%_200%]"
            />
          )}
        </AnimatePresence>

        {/* Icon / Status Indicator */}
        <div className="mr-4 flex-shrink-0 flex items-center justify-center">
          <div className="relative flex items-center justify-center w-[44px] h-[44px]">
             {isDrafting ? (
               <Sparkle weight="fill" className="text-[#99f7ff] animate-spin-slow" size={24} />
             ) : (
               <Sparkle
                 weight="fill"
                 className={cn(
                   "transition-all duration-500",
                   isFocused || prompt.length > 0 ? "text-[#99f7ff] scale-110 drop-shadow-[0_0_10px_rgba(153,247,255,0.6)]" : "text-white/40"
                 )}
                 size={24}
               />
             )}
          </div>
        </div>

        {/* Input Area */}
        <form onSubmit={handleSubmit} className="flex-grow flex items-center min-w-0 mr-4">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            onKeyDown={handleKeyDown}
            disabled={isDrafting}
            placeholder="Draft a risk-mitigation strategy..."
            className={cn(
              "w-full bg-transparent border-none focus:ring-0 text-white",
              "placeholder:text-white/30 font-body tracking-wide text-sm outline-none",
              "disabled:opacity-50"
            )}
            style={{ minHeight: '44px' }}
          />
        </form>

        {/* Metadata & Action */}
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="hidden md:flex flex-col items-end mr-2">
            <span className="font-mono text-[10px] text-white/40 uppercase tracking-widest leading-tight">
              {isDrafting ? "Groq is thinking..." : "Parsing Quant Logic..."}
            </span>
            <span className={cn(
              "font-mono text-[11px] font-bold tracking-wider leading-tight",
              quotaRemaining > 0 ? "text-[#99f7ff]" : "text-[#ff716c]"
            )}>
              Mock Draft Quota: {quotaRemaining}/5
            </span>
          </div>

          <button
            type="button"
            onClick={() => setPrompt("")}
            disabled={isDrafting || prompt.length === 0}
            className="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Clear draft prompt"
          >
            <X size={16} />
          </button>

          <button
            type="submit"
            disabled={isDrafting || !prompt.trim() || quotaRemaining <= 0}
            className={cn(
              "flex items-center justify-center min-h-[44px] min-w-[44px] md:px-6 rounded-[2.5rem] font-headline font-bold text-sm text-[#0e0e10]",
              "transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100",
              "bg-[linear-gradient(135deg,#67e8f9_0%,#34d399_150%)] hover:shadow-[0_0_20px_rgba(52,211,153,0.35)]"
            )}
            aria-label="Submit Draft"
          >
            <span className="hidden md:inline">{isDrafting ? "Drafting..." : "Draft"}</span>
            {!isDrafting && <Lightning weight="fill" className="md:ml-2" size={16} />}
            {isDrafting && <Sparkle weight="fill" className="md:hidden animate-spin-slow" size={16} />}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
