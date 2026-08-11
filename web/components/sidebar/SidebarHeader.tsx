"use client";

import { PanelLeft, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";
import { Tooltip } from "@/components/ui/Tooltip";

export type SidebarVariant = "rail" | "drawer";

/**
 * Sidebar brand row.
 *
 * Rail keeps the square-drawer icon that desktop already knows, swapping to the
 * Argus mark only while collapsed. Drawer separates the two roles the spec
 * calls out: the mark is a static logo, and the control is an X that says what
 * it does. A brand mark that is also a control is ambiguous.
 */
export default function SidebarHeader({
  variant,
  isOpen,
  onToggle,
  onRequestClose,
}: {
  variant: SidebarVariant;
  isOpen: boolean;
  onToggle: () => void;
  onRequestClose?: () => void;
}) {
  const { t } = useTranslation();

  if (variant === "drawer") {
    return (
      <div className="flex h-20 items-center justify-between gap-2 px-3 pb-4 pt-6">
        <div className="flex min-w-0 items-center gap-2">
          <ArgusLogo
            className="h-8 w-8 shrink-0 text-black dark:text-white"
            aria-hidden="true"
            data-testid="sidebar-drawer-logo"
          />
          <span className="font-display truncate text-[22px] font-medium tracking-tight text-black dark:text-white">
            argus
          </span>
        </div>
        <button
          type="button"
          onClick={onRequestClose}
          data-testid="sidebar-drawer-close"
          aria-label={t("sidebar.close", "Close sidebar")}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
        >
          <X className="h-5 w-5 text-black/60 dark:text-white/60" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-20 items-center px-[6px] pb-4 pt-6">
      <Tooltip
        content={isOpen ? t("sidebar.close", "Close sidebar") : t("sidebar.open", "Open sidebar")}
        side="right"
        delay={150}
      >
        <button
          onClick={onToggle}
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
          aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          {/* Swap: PanelLeft when open → ArgusLogo when collapsed */}
          {isOpen ? (
            <PanelLeft className="h-5 w-5 text-black/60 dark:text-white/60" />
          ) : (
            <ArgusLogo className="h-8 w-8 text-black dark:text-white" />
          )}
        </button>
      </Tooltip>
      {/* "argus" text — font-display (Space Grotesk) per DESIGN.md */}
      <span
        className={`ml-1 whitespace-nowrap font-display text-[22px] font-medium tracking-tight text-black transition-[opacity,max-width] duration-300 ease-in-out dark:text-white ${
          isOpen ? "max-w-[200px] opacity-100" : "max-w-0 overflow-hidden opacity-0"
        }`}
      >
        argus
      </span>
    </div>
  );
}
