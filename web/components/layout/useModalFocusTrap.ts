"use client";

import { useCallback, useEffect, useRef, type RefObject } from "react";
import { hasOverlayAbove } from "./overlayStack";

/**
 * Focus behavior every `aria-modal` surface owes its keyboard users.
 *
 * Declaring `aria-modal` is a promise that the rest of the page is inert. The
 * sheet kept that promise and the drawer did not, which is exactly the drift a
 * shared hook prevents: an unmanaged modal leaves focus on the opener behind
 * the scrim, and because an overlay usually precedes its trigger in DOM order,
 * the next Tab walks obscured controls instead of entering the panel.
 */

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/** Wraps at both ends so focus never escapes an open modal. */
export function nextFocusIndex({
  count,
  currentIndex,
  direction,
}: {
  count: number;
  currentIndex: number;
  direction: "focus-next" | "focus-previous";
}): number {
  if (count <= 0) return -1;
  if (direction === "focus-next") {
    return currentIndex >= count - 1 || currentIndex < 0 ? 0 : currentIndex + 1;
  }
  return currentIndex <= 0 ? count - 1 : currentIndex - 1;
}

export function useModalFocusTrap({
  isOpen,
  overlayId,
  containerRef,
  initialFocusRef,
}: {
  isOpen: boolean;
  /** Identity in the overlay stack, so a parent trap can stand down. */
  overlayId: string;
  containerRef: RefObject<HTMLElement | null>;
  /** Where focus lands on open; the first focusable child otherwise. */
  initialFocusRef?: RefObject<HTMLElement | null>;
}): void {
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  const focusableElements = useCallback((): HTMLElement[] => {
    const container = containerRef.current;
    if (!container) return [];
    return Array.from(
      container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((element) => element.offsetParent !== null);
  }, [containerRef]);

  useEffect(() => {
    if (!isOpen) return;
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const target = initialFocusRef?.current ?? focusableElements()[0] ?? null;
    target?.focus();
    return () => {
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [focusableElements, initialFocusRef, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      // A parent trap runs first and would move focus, then the modal above it
      // would see the moved focus and wrap, so forward Tab never advanced.
      if (hasOverlayAbove(overlayId)) return;
      const elements = focusableElements();
      if (elements.length === 0) return;
      event.preventDefault();
      const index = nextFocusIndex({
        count: elements.length,
        currentIndex: elements.indexOf(document.activeElement as HTMLElement),
        direction: event.shiftKey ? "focus-previous" : "focus-next",
      });
      elements[index]?.focus();
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [focusableElements, isOpen, overlayId]);
}
