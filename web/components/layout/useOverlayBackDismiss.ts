"use client";

import { useEffect, useRef } from "react";
import { hasOverlayAbove } from "./overlayStack";

/**
 * System back closes the overlay instead of leaving Argus.
 *
 * `display: standalone` removes the browser back button, so an installed user
 * has no chrome-level way out of a drawer or sheet. Android still sends its
 * hardware back through `popstate`; opening an overlay pushes one same-URL
 * history entry so that press lands here rather than exiting the app. iOS
 * standalone has no back at all, which is why every overlay also carries a
 * visible close control.
 */

export const OVERLAY_HISTORY_KEY = "argusOverlay";

/**
 * Overlays that pushed a history entry and have not yet spent it.
 *
 * Ownership cannot live in `history.state`: Next's App Router calls
 * `replaceState` with its own routing tree and drops foreign keys, so the
 * marker was always gone by the time a `popstate` arrived.
 *
 * Whoever claims the id first wins. A `popstate` that finds the id already
 * claimed is the echo of our own `history.back()`, so it is ignored; one that
 * still finds it is a user pressing back.
 */
let unconsumedOverlays: string[] = [];

/**
 * Traversals we asked for and are still waiting on.
 *
 * A closing overlay spends its entry by calling back(), and the resulting event
 * reaches every listener, including the parent underneath, which by then is
 * topmost and would read it as a real back press. That is how dismissing a
 * language modal closed the drawer behind it.
 *
 * Suppression used to expire on the next animation frame. Nothing guarantees
 * `popstate` arrives inside a frame, and Chromium can run the frame first, so
 * the parent saw an unsuppressed event and closed as well, at random. Waiting
 * for the traversal itself is the only deadline that means anything.
 *
 * The count only ever falls when the event we were waiting for shows up, and
 * `handledPops` makes that decision once per event so every listener for it
 * agrees. The timeout is a safety net, not the mechanism: `back()` at the start
 * of session history is a no-op that sends nothing, and without it that would
 * swallow the user's next real press forever.
 */
let pendingProgrammaticPops = 0;
let programmaticPopExpiry: ReturnType<typeof setTimeout> | null = null;
let handledPops = new WeakSet<Event>();

/** Far longer than any real traversal; only reached when none is coming. */
const PROGRAMMATIC_POP_TIMEOUT_MS = 2000;

function clearProgrammaticPopExpiry(): void {
  if (programmaticPopExpiry === null) return;
  clearTimeout(programmaticPopExpiry);
  programmaticPopExpiry = null;
}

/**
 * Spends pending traversals even when no overlay is left to notice them.
 *
 * Closing the last overlay by its own control removes that overlay's listener
 * before the deferred `back()` runs, so nothing was there to classify the event
 * and the count sat pending until it timed out. Reopening an overlay inside
 * that window and pressing Android back read the real press as our own echo,
 * and the overlay stayed put.
 *
 * This listener is never removed, so a traversal is always observed by someone.
 * Order against the overlay listeners does not matter: whichever runs first
 * spends the traversal and records the event, and the rest read that back.
 */
let popClassifierInstalled = false;

function installPopClassifier(): void {
  if (popClassifierInstalled || typeof window === "undefined") return;
  popClassifierInstalled = true;
  window.addEventListener("popstate", (event) => {
    isProgrammaticPop(event);
  });
}

export function markProgrammaticPop(): void {
  installPopClassifier();
  pendingProgrammaticPops += 1;
  clearProgrammaticPopExpiry();
  programmaticPopExpiry = setTimeout(() => {
    programmaticPopExpiry = null;
    pendingProgrammaticPops = 0;
  }, PROGRAMMATIC_POP_TIMEOUT_MS);
}

/**
 * Whether this `popstate` is the echo of a back() we asked for.
 *
 * Classification is per event, not per caller: the first listener to ask spends
 * one pending traversal, and the rest read the same answer back out.
 */
export function isProgrammaticPop(event: Event): boolean {
  if (handledPops.has(event)) return true;
  if (pendingProgrammaticPops === 0) return false;
  pendingProgrammaticPops -= 1;
  handledPops.add(event);
  if (pendingProgrammaticPops === 0) clearProgrammaticPopExpiry();
  return true;
}

/** Test seam: reset document-level state between cases. */
export function resetOverlayEntries(): void {
  unconsumedOverlays = [];
  pendingProgrammaticPops = 0;
  handledPops = new WeakSet<Event>();
  clearProgrammaticPopExpiry();
}

export function claimOverlayEntry(overlayId: string): boolean {
  if (!unconsumedOverlays.includes(overlayId)) return false;
  unconsumedOverlays = unconsumedOverlays.filter((id) => id !== overlayId);
  return true;
}

export function recordOverlayEntry(overlayId: string): void {
  unconsumedOverlays = [...unconsumedOverlays, overlayId];
}

export function openOverlayEntries(): readonly string[] {
  return unconsumedOverlays;
}

/**
 * Consume every outstanding entry without popping any of them.
 *
 * A navigation out of an overlay writes the destination onto the entry the
 * overlay pushed, using `replaceState`. Popping that entry afterwards restores
 * the URL the overlay opened over, leaving the address bar pointing at the
 * conversation the user just left while the transcript shows the new one, and a
 * reload lands on the wrong one. The entry is not spare, it is the destination.
 */
export function consumeOverlayEntriesForNavigation(): void {
  unconsumedOverlays = [];
}

export function overlayHistoryState(
  currentState: unknown,
  overlayId: string,
): Record<string, unknown> {
  const base =
    currentState && typeof currentState === "object"
      ? (currentState as Record<string, unknown>)
      : {};
  return { ...base, [OVERLAY_HISTORY_KEY]: overlayId };
}

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

  useEffect(() => {
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
