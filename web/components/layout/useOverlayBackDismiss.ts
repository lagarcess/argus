"use client";

import { useEffect, useLayoutEffect, useRef } from "react";
import { hasOverlayAbove } from "./overlayStack";
import {
  claimOverlayEntry,
  isProgrammaticPop,
  markProgrammaticPop,
  openOverlayEntries,
  overlayHistoryState,
  recordOverlayEntry,
} from "@/lib/overlay-history";

/**
 * System back closes the overlay instead of leaving Argus.
 *
 * The entry bookkeeping this depends on lives in `lib/overlay-history`, because
 * it is browser-history state rather than a React concern, and because the
 * routing code that rewrites the URL has to invalidate those entries without
 * reaching into a component module to do it.
 */

export {
  OVERLAY_HISTORY_KEY,
  claimOverlayEntry,
  consumeOverlayEntriesForNavigation,
  isProgrammaticPop,
  markProgrammaticPop,
  openOverlayEntries,
  overlayHistoryState,
  recordOverlayEntry,
  resetOverlayEntries,
} from "@/lib/overlay-history";

/** `useLayoutEffect` warns during SSR, where there is nothing to sync. */
const useIsomorphicLayoutEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

export function useOverlayBackDismiss({
  isOpen,
  overlayId,
  onDismiss,
  canDismiss,
}: {
  isOpen: boolean;
  overlayId: string;
  onDismiss: () => void;
  /**
   * Whether the overlay will accept a dismissal right now.
   *
   * Declining inside `onDismiss` is too late: the entry has already been
   * claimed by then, so the overlay stayed open holding an id it had already
   * spent. Every later press found nothing to claim, and the overlay could
   * never be closed by back again while it blocked its parents from answering.
   */
  canDismiss?: () => boolean;
}): void {
  const dismissRef = useRef(onDismiss);
  const canDismissRef = useRef(canDismiss);
  const pendingPopRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /*
   * Layout timing, as the keyboard registry already uses. A passive effect runs
   * after paint, so a back press landing between commit and flush reached the
   * previous render's closures: a confirmation that had just gone busy was
   * still judged by the pre-busy guard, which is the case the guard exists for.
   */
  useIsomorphicLayoutEffect(() => {
    dismissRef.current = onDismiss;
    canDismissRef.current = canDismiss;
  }, [canDismiss, onDismiss]);

  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return;

    // A remount lands here before the previous cleanup's pop has run, so cancel
    // it: React double-invoking an effect is not the user closing anything.
    if (pendingPopRef.current !== null) {
      clearTimeout(pendingPopRef.current);
      pendingPopRef.current = null;
    }

    // Push at most one entry per open overlay. Without this a remount stacks a
    // second entry that nothing will ever pop.
    if (!openOverlayEntries().includes(overlayId)) {
      recordOverlayEntry(overlayId);
      window.history.pushState(
        overlayHistoryState(window.history.state, overlayId),
        "",
        window.location.href,
      );
    }

    const handlePopState = (event: PopStateEvent) => {
      // An overlay closing above us spends its entry with back(); that event is
      // not a user pressing back and must reach nobody.
      if (isProgrammaticPop(event)) return;
      // One press, one level. Every nested listener hears the same event, so
      // without this each would claim its own id and dismiss together.
      if (hasOverlayAbove(overlayId)) return;
      if (canDismissRef.current && !canDismissRef.current()) {
        // Refused, and the traversal is already spent. Put an entry back or the
        // next press walks past this overlay and out of Argus.
        window.history.pushState(
          overlayHistoryState(window.history.state, overlayId),
          "",
          window.location.href,
        );
        return;
      }
      // Already claimed means this is the echo of our own back() below.
      if (!claimOverlayEntry(overlayId)) return;
      dismissRef.current();
    };
    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      // Deferred so a remount can cancel it. A real close has nothing to cancel
      // it, so the entry is spent on the next tick and the stack stays flat.
      pendingPopRef.current = setTimeout(() => {
        pendingPopRef.current = null;
        if (!claimOverlayEntry(overlayId)) return;
        markProgrammaticPop();
        window.history.back();
      }, 0);
    };
  }, [isOpen, overlayId]);
}
