"use client";

import { useEffect, useMemo, useState } from "react";
import {
  isQuickJumpModifierActive,
  quickJumpIndexForEvent,
  type KeyboardShortcutEvent,
} from "@/lib/keyboard-shortcuts";

export type QuickJumpItem = {
  id: string;
  pinned?: boolean;
};

export type NumberedQuickJumpItem<T extends QuickJumpItem> = T & {
  number: number;
};

export function numberQuickJumpItems<T extends QuickJumpItem>(
  items: readonly T[],
): readonly NumberedQuickJumpItem<T>[] {
  const pinned = items.filter((item) => item.pinned);
  const unpinned = items.filter((item) => !item.pinned);
  return [...pinned, ...unpinned]
    .slice(0, 9)
    .map((item, index) => ({ ...item, number: index + 1 }));
}

export function quickJumpItemForEvent<T extends QuickJumpItem>(
  items: readonly T[],
  event: KeyboardShortcutEvent,
  usesCommandKey: boolean,
): NumberedQuickJumpItem<T> | null {
  const index = quickJumpIndexForEvent(event, usesCommandKey);
  if (index === null) return null;
  return numberQuickJumpItems(items)[index] ?? null;
}

type UseQuickJumpOptions<T extends QuickJumpItem> = {
  enabled: boolean;
  items: readonly T[];
  onSelect: (id: string) => void;
  usesCommandKey: boolean;
};

export function useQuickJump<T extends QuickJumpItem>({
  enabled,
  items,
  onSelect,
  usesCommandKey,
}: UseQuickJumpOptions<T>) {
  const [isQuickJumpActive, setIsQuickJumpActive] = useState(false);
  const numberedItems = useMemo(() => numberQuickJumpItems(items), [items]);

  useEffect(() => {
    if (!enabled) {
      setIsQuickJumpActive(false);
      return;
    }

    const updateActive = (event: KeyboardShortcutEvent) => {
      setIsQuickJumpActive(
        isQuickJumpModifierActive(event, usesCommandKey),
      );
    };
    const onKeyDown = (event: KeyboardEvent) => {
      updateActive(event);
      const item = quickJumpItemForEvent(items, event, usesCommandKey);
      if (!item) return;
      event.preventDefault();
      onSelect(item.id);
    };
    const onKeyUp = (event: KeyboardEvent) => updateActive(event);
    const onBlur = () => setIsQuickJumpActive(false);

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
    };
  }, [enabled, items, onSelect, usesCommandKey]);

  return {
    isQuickJumpActive,
    numberFor: (id: string): number | null =>
      numberedItems.find((item) => item.id === id)?.number ?? null,
  };
}
