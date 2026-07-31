import { quickJumpHintDisplay } from "@/lib/keyboard-shortcuts";
import { KeyboardShortcutKeycap } from "./KeyboardShortcutKeycap";

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
      <KeyboardShortcutKeycap>
        {quickJumpHintDisplay(number, usesCommandKey)}
      </KeyboardShortcutKeycap>
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
