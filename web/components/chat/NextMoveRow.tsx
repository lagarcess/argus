"use client";

import type { ReactNode } from "react";

type NextMoveRowProps = {
  ariaLabel?: string;
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
};

/**
 * One conversational next move: a clarify option, a discovery candidate, or a
 * follow-up. Borderless at rest; hover tints the arrow and title together with
 * muted teal (#5ba897, --rui-color-teal) -- no box, no shadow. The hit area
 * spans the full column at >=44px tall.
 *
 * `disabled` mirrors the composer's in-flight lock: the row stays readable
 * because it is evidence, but stops accepting taps while a turn is running.
 */
export default function NextMoveRow({
  ariaLabel,
  children,
  disabled = false,
  onClick,
}: NextMoveRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className="group/next-move flex min-h-11 w-full items-start gap-1.5 text-start disabled:cursor-default disabled:opacity-55"
    >
      <span
        aria-hidden="true"
        className={`mt-[9px] shrink-0 text-[13px] leading-[1.5] text-black/35 transition-colors rtl:-scale-x-100 dark:text-white/35 ${
          disabled
            ? ""
            : "group-hover/next-move:text-[#5ba897] group-active/next-move:text-[#5ba897] dark:group-hover/next-move:text-[#5ba897] dark:group-active/next-move:text-[#5ba897]"
        }`}
      >
        ↳
      </span>
      <span className="argus-next-move-text min-w-0 py-2 text-[14px] leading-[1.5] tracking-tight text-black/80 [overflow-wrap:anywhere] dark:text-white/80">
        {children}
      </span>
    </button>
  );
}

/** Row title; brightens with the arrow on hover so the row reads as one action. */
export function NextMoveTitle({ children }: { children: ReactNode }) {
  return (
    <span className="font-medium text-black/80 transition-colors group-hover/next-move:text-[#5ba897] group-active/next-move:text-[#5ba897] dark:text-white/85 dark:group-hover/next-move:text-[#5ba897] dark:group-active/next-move:text-[#5ba897]">
      {children}
    </span>
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

/**
 * The resolver-verified ticker, as an object in the sentence rather than
 * punctuation around it: one step off the surface, hairline bordered, quiet
 * enough that the sentence stays the loudest thing in the row.
 */
export function NextMoveTicker({ children }: { children: string }) {
  return (
    <span className="mx-[3px] inline-flex translate-y-[-1px] items-center rounded-[5px] border border-black/10 bg-black/[0.04] px-1.5 py-px align-middle font-mono text-[11px] font-normal leading-[1.4] tracking-[0.02em] text-black/55 dark:border-white/12 dark:bg-white/[0.06] dark:text-white/55">
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
