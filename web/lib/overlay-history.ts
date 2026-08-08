
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
 * For classifying one, order against the overlay listeners does not matter:
 * whichever runs first spends the traversal and records the event, and the rest
 * read that back. Skipping a duplicate does depend on running first, which
 * `skipOverlayDuplicate` explains and relies on.
 *
 * What is held here is the window the listener is on, rather than whether one
 * was ever added. A boolean assumed there is only ever one window, which holds
 * in a browser and not in a test file that stands its own up: the flag was
 * already true from an earlier file, so the listener stayed attached to a
 * window that had been thrown away and this one silently had none.
 */
let popClassifierWindow: unknown = null;

function installPopClassifier(): void {
  if (typeof window === "undefined" || popClassifierWindow === window) return;
  popClassifierWindow = window;
  window.addEventListener("popstate", (event) => {
    if (isProgrammaticPop(event)) return;
    skipOverlayDuplicate();
  });
}

/**
 * Same-URL entries left underneath a destination when a nested overlay
 * navigated away.
 *
 * Only the entry the topmost overlay pushed becomes the destination. The ones
 * below it are exact copies of the URL the overlays opened over, and the
 * History API has no way to delete an entry, so back landed on one and looked
 * like it had done nothing: Omnisearch, then a dossier, then Open conversation
 * cost the user a dead press.
 *
 * They are spent on the next real back press rather than removed. Stepping
 * past one can never skip a page, because an overlay pushes `location.href`
 * unchanged and every duplicate is therefore identical to the entry beneath
 * it. The href is kept alongside so a press that lands somewhere else, after
 * the user has navigated on from the destination, is left alone.
 */
let overlayDuplicateHrefs: string[] = [];

/**
 * Carries a back press past a duplicate so one press stays one step.
 *
 * Only while no overlay is open: with one open the press belongs to it.
 * Reading that from the entries rather than from the layer registry keeps this
 * module free of a runtime dependency on the React side, and holds because the
 * classifier observes the event before any overlay does. Recording a duplicate
 * installs the classifier, so by the time there is ever anything to skip, this
 * listener is already the older of the two. Anything that would register the
 * classifier later has to keep that true.
 */
function skipOverlayDuplicate(): void {
  if (typeof window === "undefined") return;
  if (unconsumedOverlays.length > 0) return;
  const duplicateHref = overlayDuplicateHrefs[overlayDuplicateHrefs.length - 1];
  if (duplicateHref === undefined) return;
  if (duplicateHref !== window.location.href) return;
  overlayDuplicateHrefs.pop();
  markProgrammaticPop();
  window.history.back();
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
  overlayDuplicateHrefs = [];
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
 *
 * Only the topmost one is the destination, though. Nested overlays each pushed
 * an entry, and the ones underneath become duplicates that nothing will ever
 * pop, so they are handed to `skipOverlayDuplicate` to spend on the next back
 * press. Recorded here rather than collapsed here: undoing them needs a
 * traversal, and a traversal cannot be awaited without leaving the destination
 * URL unwritten in the meantime, which is the failure this whole function
 * exists to prevent.
 */
export function consumeOverlayEntriesForNavigation(): void {
  const duplicates = Math.max(0, unconsumedOverlays.length - 1);
  unconsumedOverlays = [];
  if (duplicates === 0 || typeof window === "undefined") return;
  // Called before the destination is written, so this is still the URL the
  // overlays opened over, which is what those entries hold.
  const href = window.location.href;
  installPopClassifier();
  for (let index = 0; index < duplicates; index += 1) {
    overlayDuplicateHrefs.push(href);
  }
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
