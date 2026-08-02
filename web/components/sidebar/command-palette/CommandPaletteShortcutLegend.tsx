"use client";

import { useEffect, useState } from "react";
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
  hasManageActions,
  usesCommandKey,
}: {
  hasManageActions: boolean;
  usesCommandKey: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div
      className="flex min-w-0 items-center justify-center gap-1.5 text-[11px] text-black/45 dark:text-white/50"
      data-command-palette-shortcut-legend
    >
      <span className="whitespace-nowrap">{t("command_palette.shortcut_legend.go", "Go")}</span>
      <KeyboardShortcutKeycap>↵</KeyboardShortcutKeycap>
      <span className="whitespace-nowrap">{t("command_palette.shortcut_legend.open_left_off", "Continue")}</span>
      <KeyboardShortcutKeycap>{usesCommandKey ? "⌘↵" : "Ctrl+Enter"}</KeyboardShortcutKeycap>
      {hasManageActions && <>
        <span className="whitespace-nowrap">{t("command_palette.shortcut_legend.rename", "Rename")}</span>
        <KeyboardShortcutKeycap>{keyboardShortcutHintDisplay("command_palette_rename", usesCommandKey)}</KeyboardShortcutKeycap>
        <span className="whitespace-nowrap">{t("command_palette.shortcut_legend.archive", "Archive")}</span>
        <KeyboardShortcutKeycap>{keyboardShortcutHintDisplay("command_palette_archive", usesCommandKey)}</KeyboardShortcutKeycap>
        <span className="whitespace-nowrap">{t("command_palette.shortcut_legend.delete", "Delete")}</span>
        <KeyboardShortcutKeycap>{keyboardShortcutHintDisplay("command_palette_delete", usesCommandKey)}</KeyboardShortcutKeycap>
      </>}
    </div>
  );
}
