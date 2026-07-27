"use client";

import type { ReactNode } from "react";

type NextMoveRowProps = {
  ariaLabel?: string;
  children: ReactNode;
  onClick: () => void;
};

/**
 * One conversational next move: a clarify option, a discovery candidate, or a
 * follow-up. Borderless at rest — the `↳` glyph carries the affordance, which
 * touch devices need because they never hover. The hover/press wash hugs the
 * text, while the hit area spans the full column and stays at least 44px tall.
 */
export default function NextMoveRow({
  ariaLabel,
  children,
  onClick,
}: NextMoveRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className="group/next-move flex min-h-11 w-full items-start gap-1.5 text-start"
    >
      <span
        aria-hidden="true"
        className="mt-[9px] shrink-0 text-[13px] leading-[1.5] text-black/35 rtl:-scale-x-100 dark:text-white/35"
      >
        ↳
      </span>
      <span className="my-1 min-w-0 rounded-[9px] border border-transparent px-2 py-1 text-[14px] leading-[1.5] tracking-tight text-black/80 transition-colors [overflow-wrap:anywhere] group-hover/next-move:border-black/12 group-hover/next-move:bg-black/5 group-active/next-move:border-black/12 group-active/next-move:bg-black/5 dark:text-white/80 dark:group-hover/next-move:border-white/12 dark:group-hover/next-move:bg-white/6 dark:group-active/next-move:border-white/12 dark:group-active/next-move:bg-white/6">
        {children}
      </span>
    </button>
  );
}

/** Muted separator between row segments; kept a node so locales can restyle it. */
export function NextMoveSeparator({ children }: { children: string }) {
  return (
    <span aria-hidden="true" className="px-1 text-black/30 dark:text-white/30">
      {children}
    </span>
  );
}

/** Secondary row text (resolver-owned name, reason). Always wraps, never clipped. */
export function NextMoveDetail({ children }: { children: ReactNode }) {
  return (
    <span className="text-black/55 dark:text-white/55">{children}</span>
  );
}
