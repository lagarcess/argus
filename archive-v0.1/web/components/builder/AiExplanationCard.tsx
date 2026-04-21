"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Info, X } from "lucide-react";

interface AiExplanationCardProps {
  explanation?: string | null;
  onClose?: () => void;
}

export function AiExplanationCard({ explanation, onClose }: AiExplanationCardProps) {
  return (
    <AnimatePresence>
      {explanation && (
        <motion.div
          initial={{ opacity: 0, x: 20, y: -20 }}
          animate={{ opacity: 1, x: 0, y: 0 }}
          exit={{ opacity: 0, x: 20, y: -20 }}
          transition={{ type: "spring", stiffness: 400, damping: 25 }}
          data-testid="ai-explanation-card"
          className="absolute top-24 right-4 md:right-8 z-40 w-[90%] md:max-w-sm"
        >
          <div className="relative p-4 rounded-[1.5rem] bg-[#262528]/80 backdrop-blur-xl border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.4)]">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 text-[#99f7ff]">
                <Info size={18} />
              </div>
              <div className="flex-1">
                <h4 className="font-mono text-[10px] text-white/50 uppercase tracking-widest mb-1">
                  AI Drafter Reasoning
                </h4>
                <p data-testid="ai-explanation-text" className="font-body text-sm text-slate-200 leading-relaxed italic">
                  "{explanation}"
                </p>
              </div>
              {onClose && (
                <button
                  onClick={onClose}
                  className="text-white/30 hover:text-white transition-colors flex items-center justify-center min-w-[44px] min-h-[44px]"
                  aria-label="Close AI Explanation"
                >
                  <X size={16} />
                </button>
              )}
            </div>
            {/* Liquid Glass Refraction Glow */}
            <div className="absolute inset-0 rounded-[1.5rem] border border-[#99f7ff]/20 pointer-events-none opacity-50 mix-blend-overlay" />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
