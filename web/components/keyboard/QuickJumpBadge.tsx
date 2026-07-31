import { quickJumpHintDisplay } from "@/lib/keyboard-shortcuts";

type QuickJumpBadgeProps = {
  number: number;
  presentation?: "badge" | "shortcut_hint";
  usesCommandKey?: boolean;
};

export function QuickJumpBadge({
  number,
  presentation = "badge",
  usesCommandKey = false,
}: QuickJumpBadgeProps) {
  if (presentation === "shortcut_hint") {
    return (
      <span
        aria-hidden="true"
        className="font-mono text-[11px] font-medium tracking-tight text-black/30 dark:text-white/30"
      >
        {quickJumpHintDisplay(number, usesCommandKey)}
      </span>
    );
  }

  return (
    <span
      aria-hidden="true"
      className="flex h-5 min-w-5 items-center justify-center rounded-md border border-black/10 bg-black/[0.04] px-1 font-sans text-[10px] font-semibold text-black/60 dark:border-white/15 dark:bg-white/[0.08] dark:text-white/70"
    >
      {number}
    </span>
  );
}
