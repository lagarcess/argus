"use client";

import { useEffect, useRef, type RefObject } from "react";
import { FOCUSABLE_SELECTOR, focusableWithin } from "./overlayFocus";

export { nextFocusIndex } from "./overlayFocus";

/**
 * Where focus goes when a modal opens, and where it returns when one closes.
 *
 * Tab containment is not here. It used to be, as a document listener per
 * modal, and that is what let Tab escape a dialog nested in the drawer: the
 * parent's listener ran first, moved focus, and the dialog above it then saw
 * the moved focus and wrapped. Containment belongs to whichever layer is
 * topmost, which only the registry knows, so it lives there.
 */
export function useModalFocusTrap({
  isOpen,
  containerRef,
  initialFocusRef,
  returnFocusRef,
}: {
  isOpen: boolean;
  containerRef: RefObject<HTMLElement | null>;
  /** Where focus lands on open; the first focusable child otherwise. */
  initialFocusRef?: RefObject<HTMLElement | null>;
  /**
   * Where focus lands on close when the opener is gone.
   *
   * Closing a modal opened from the drawer can unmount the drawer with it, and
   * restoring to a detached node drops focus to the body.
   */
  returnFocusRef?: RefObject<HTMLElement | null>;
}): void {
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const target =
      initialFocusRef?.current ?? focusableWithin(containerRef.current)[0] ?? null;
    target?.focus();
    return () => {
      const opener = restoreFocusRef.current;
      restoreFocusRef.current = null;
      const openerIsPageRoot =
        opener === document.body || opener === document.documentElement;
      if (opener?.isConnected && !openerIsPageRoot) {
        opener.focus();
        return;
      }
      // Read at cleanup on purpose: the fallback matters precisely when the
      // opener has gone, so the value at close is the one that counts.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const root = returnFocusRef?.current ?? null;
      const fallback = root?.matches(FOCUSABLE_SELECTOR)
        ? root
        : root?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      fallback?.focus();
    };
  }, [containerRef, initialFocusRef, isOpen, returnFocusRef]);
}
