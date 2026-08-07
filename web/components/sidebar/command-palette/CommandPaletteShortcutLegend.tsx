"use client";

import { useEffect, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { KeyboardShortcutKeycap } from "@/components/keyboard/KeyboardShortcutKeycap";
import {
  isKeyboardShortcutHintModifierActive,
  keyboardShortcutHintDisplay,
} from "@/lib/keyboard-shortcuts";

export function useCommandPaletteShortcutLegend() {
  const [usesCommandKey, setUsesCommandKey] = useState(false);
  const [isModifierActive, setIsModifierActive] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const nextUsesCommandKey = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    setUsesCommandKey(nextUsesCommandKey);
    const update = (event: KeyboardEvent) =>
      setIsModifierActive(
        isKeyboardShortcutHintModifierActive(event, nextUsesCommandKey),
      );
    const clear = () => setIsModifierActive(false);
    document.addEventListener("keydown", update);
    document.addEventListener("keyup", update);
    window.addEventListener("blur", clear);
    return () => {
      document.removeEventListener("keydown", update);
      document.removeEventListener("keyup", update);
      window.removeEventListener("blur", clear);
    };
  }, []);

  return {
    isVisible: isHovered && isModifierActive,
    usesCommandKey,
    actionRegionProps: {
      onMouseEnter: () => setIsHovered(true),
      onMouseLeave: () => setIsHovered(false),
    },
  };
}

export function CommandPaletteShortcutLegend({
  compact = false,
  hasManageActions,
  usesCommandKey,
}: {
  compact?: boolean;
  hasManageActions: boolean;
  usesCommandKey: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div
      className={`hidden min-w-0 items-center font-medium text-black/70 md:flex dark:text-white/70 ${
        compact ? "gap-2 text-[11px]" : "gap-4 text-[12px]"
      }`}
      data-command-palette-shortcut-legend
    >
      <ShortcutAction
        compact={compact}
        label={t("command_palette.shortcut_legend.go", "Go")}
        shortcut="↵"
      />
      {hasManageActions && (
        <>
          <ShortcutAction
            compact={compact}
            label={t("command_palette.shortcut_legend.rename", "Rename")}
            shortcut={keyboardShortcutHintDisplay(
              "command_palette_rename",
              usesCommandKey,
            )}
          />
          <ShortcutAction
            compact={compact}
            label={t("command_palette.shortcut_legend.archive", "Archive")}
            shortcut={keyboardShortcutHintDisplay(
              "command_palette_archive",
              usesCommandKey,
            )}
          />
          <ShortcutAction
            compact={compact}
            label={t("command_palette.shortcut_legend.delete", "Delete")}
            shortcut={keyboardShortcutHintDisplay(
              "command_palette_delete",
              usesCommandKey,
            )}
          />
        </>
      )}
    </div>
  );
}

function ShortcutAction({
  compact,
  label,
  shortcut,
}: {
  compact: boolean;
  label: string;
  shortcut: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap ${
        compact ? "gap-1" : "gap-1.5"
      }`}
      data-command-palette-shortcut-action
    >
      <span>{label}</span>
      <KeyboardShortcutKeycap
        className={`!h-6 !min-w-0 !rounded-md !border !border-black/10 !bg-black/[0.025] !text-[11px] !text-black/55 dark:!border-white/12 dark:!bg-white/[0.06] dark:!text-white/65 ${
          compact ? "!px-1.5" : "!px-2"
        }`}
      >
        {shortcut}
      </KeyboardShortcutKeycap>
    </span>
  );
}

export function CommandPaletteFooter({
  footerCount,
  hasManageActions,
  isFiltering,
  isLedgerMode,
  layoutMode,
  onToggleLayout,
  shortcutLegendVisible,
  usesCommandKey,
}: {
  footerCount: number;
  hasManageActions: boolean;
  isFiltering: boolean;
  isLedgerMode: boolean;
  layoutMode: "expanded" | "collapsed";
  /** Absent below the mobile threshold, where the layout is collapsed-only. */
  onToggleLayout?: () => void;
  shortcutLegendVisible: boolean;
  usesCommandKey: boolean;
}) {
  const { t } = useTranslation();
  const collapsedLegendVisible =
    layoutMode === "collapsed" && shortcutLegendVisible;
  return (
    <div
      className={`items-center gap-3 border-t border-black/5 px-4 py-2 dark:border-white/5 ${
        collapsedLegendVisible
          ? "flex"
          : "grid grid-cols-[minmax(0,1fr)_auto]"
      }`}
    >
      {!collapsedLegendVisible && (
        <span className="text-[11px] text-black/30 dark:text-white/30">
          {!isLedgerMode &&
            footerCount > 0 &&
            t(
              isFiltering
                ? "command_palette.result_count"
                : "command_palette.conversation_count",
              {
                count: footerCount,
                defaultValue_one: isFiltering
                  ? "{{count}} result"
                  : "{{count}} conversation",
                defaultValue_other: isFiltering
                  ? "{{count}} results"
                  : "{{count}} conversations",
              },
            )}
        </span>
      )}
      <div
        className={`flex min-w-0 items-center gap-3 ${
          collapsedLegendVisible ? "w-full justify-between" : "justify-end"
        }`}
      >
        {shortcutLegendVisible && (
          <CommandPaletteShortcutLegend
            compact={layoutMode === "collapsed"}
            hasManageActions={hasManageActions}
            usesCommandKey={usesCommandKey}
          />
        )}
        {onToggleLayout ? (
        <button
          type="button"
          onClick={onToggleLayout}
          className="flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-black/40 hover:bg-black/5 dark:text-white/40 dark:hover:bg-white/5"
        >
          {layoutMode === "expanded" ? (
            <>
              <Minimize2 className="h-3 w-3" />
              {t("common.collapse", "Collapse")}
            </>
          ) : (
            <>
              <Maximize2 className="h-3 w-3" />
              {t("common.expand", "Expand")}
            </>
          )}
        </button>
        ) : null}
      </div>
    </div>
  );
}
