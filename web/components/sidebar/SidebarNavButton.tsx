"use client";

import type { LucideIcon } from "lucide-react";

type SidebarNavButtonProps = {
  /** Lucide icon component */
  icon: LucideIcon;
  /** Button label (shown when expanded, used as tooltip when collapsed) */
  label: string;
  /** Whether this nav item is currently active */
  active?: boolean;
  /** Whether the sidebar is collapsed (icon-only mode) */
  collapsed?: boolean;
  /** Click handler */
  onClick: () => void;
  /** Optional extra class names */
  className?: string;
  /** Optional right-side content (e.g. chevron for accordion) */
  trailing?: React.ReactNode;
  /** Icon size override (default: 22) */
  iconSize?: number;
};

/**
 * Reusable sidebar navigation button.
 *
 * When collapsed: shows only the icon with a native tooltip.
 * When expanded: shows icon + label, with optional trailing element.
 */
export default function SidebarNavButton({
  icon: Icon,
  label,
  active = false,
  collapsed = false,
  onClick,
  className = "",
  trailing,
  iconSize = 22,
}: SidebarNavButtonProps) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={`group mb-1 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${
        active
          ? "bg-black/5 dark:bg-white/5"
          : "hover:bg-black/5 dark:hover:bg-white/5"
      } ${className}`}
    >
      <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center">
        <Icon
          style={{ width: iconSize, height: iconSize }}
          className="text-black/60 transition-transform duration-150 ease-out group-hover:scale-[1.06] group-hover:text-black dark:text-white/60 dark:group-hover:text-white"
        />
      </div>
      <span
        className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${
          collapsed
            ? "pointer-events-none absolute left-[72px] opacity-0"
            : "opacity-100"
        }`}
      >
        {label}
      </span>
      {trailing && (
        <div
          className={`ml-auto pr-4 transition-opacity duration-300 ${
            collapsed ? "pointer-events-none hidden opacity-0" : "opacity-100"
          }`}
        >
          {trailing}
        </div>
      )}
    </button>
  );
}
