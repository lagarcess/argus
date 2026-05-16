"use client";

import { Tooltip } from "@/components/ui/Tooltip";

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
 * Typography: Space Grotesk (font-display) per DESIGN.md Nav/UI role.
 * When collapsed: shows only the icon with a premium custom tooltip.
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
  const button = (
    <button
      onClick={onClick}
      className={`group mb-1 flex h-11 w-full items-center rounded-[14px] transition-colors duration-200 ${
        active
          ? "bg-black/5 dark:bg-white/5"
          : "hover:bg-black/5 dark:hover:bg-white/5"
      } ${className}`}
    >
      {/* Icon container: fixed 44px square, always centered */}
      <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center">
        <Icon
          style={{ width: iconSize, height: iconSize }}
          className="text-black/60 transition-transform duration-150 ease-out group-hover:scale-[1.06] group-hover:text-black dark:text-white/60 dark:group-hover:text-white"
        />
      </div>
      {/* Label: font-display (Space Grotesk) per DESIGN.md Nav/UI role */}
      <span
        className={`ml-1 whitespace-nowrap font-display text-[15px] font-medium tracking-tight text-black transition-[opacity,max-width] duration-300 ease-in-out dark:text-white ${
          collapsed
            ? "pointer-events-none max-w-0 overflow-hidden opacity-0"
            : "max-w-[180px] opacity-100"
        }`}
      >
        {label}
      </span>
      {trailing && !collapsed && (
        <div className="ml-auto pr-4">
          {trailing}
        </div>
      )}
    </button>
  );

  if (collapsed) {
    return (
      <Tooltip content={label} side="right" delay={150}>
        {button}
      </Tooltip>
    );
  }

  return button;
}
