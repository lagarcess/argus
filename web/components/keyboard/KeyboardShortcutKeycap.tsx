import type { ReactNode } from "react";

type KeyboardShortcutKeycapProps = {
  children: ReactNode;
  className?: string;
};

function isMacShortcutGlyph(value: string) {
  return value === "⌘" || value === "⌥" || value === "⌃" || value === "⇧";
}

export function KeyboardShortcutKeycap({
  children,
  className = "",
}: KeyboardShortcutKeycapProps) {
  const keys =
    typeof children === "string" &&
    Array.from(children).some(isMacShortcutGlyph)
      ? Array.from(children)
      : null;

  return (
    <span
      aria-hidden="true"
      className={`flex h-[22px] min-w-9 items-center justify-center rounded-full bg-black/[0.07] px-1.5 font-sans text-[11px] font-medium leading-4 tabular-nums text-black/55 dark:bg-white/[0.12] dark:text-white/65 ${className}`}
    >
      {keys ? (
        <span className="inline-flex items-center gap-0.5">
          {keys.map((key, index) => (
            <span key={`${key}-${index}`} className="inline-flex h-4 items-center">
              {key}
            </span>
          ))}
        </span>
      ) : (
        children
      )}
    </span>
  );
}
