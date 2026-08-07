import { afterAll, beforeAll, describe, expect, test } from "bun:test";

/**
 * A traversal has to be spent even when no overlay is left to spend it.
 *
 * Closing the last overlay through its own control removes that overlay's
 * `popstate` listener before the deferred `back()` runs, so nothing observed
 * the event and the pending count sat there until it timed out. Reopening an
 * overlay inside that window and pressing Android back read the real press as
 * our own echo, and the overlay refused to close.
 *
 * The module installs its own listener for exactly this, which needs a `window`
 * to install on. Bun has no DOM, so this file stands one up and imports the
 * module fresh against it.
 */

type Listener = (event: Event) => void;

const listeners: Listener[] = [];
let subject: typeof import("../components/layout/useOverlayBackDismiss");

beforeAll(async () => {
  (globalThis as { window?: unknown }).window = {
    addEventListener: (type: string, listener: Listener) => {
      if (type === "popstate") listeners.push(listener);
    },
    removeEventListener: () => undefined,
    history: { back: () => undefined },
  };
  subject = await import("../components/layout/useOverlayBackDismiss");
});

afterAll(() => {
  delete (globalThis as { window?: unknown }).window;
});

/** Everything listening on window, in registration order, as the DOM would. */
function dispatchPopState(): Event {
  const event = new Event("popstate");
  for (const listener of [...listeners]) listener(event);
  return event;
}

describe("programmatic pop classification", () => {
  test("installs a listener that outlives any single overlay", () => {
    subject.resetOverlayEntries();
    expect(listeners.length).toBe(0);
    subject.markProgrammaticPop();
    expect(listeners.length).toBe(1);
    // Installed once, not once per traversal.
    subject.markProgrammaticPop();
    expect(listeners.length).toBe(1);
  });

  test("an unobserved traversal is still spent", () => {
    subject.resetOverlayEntries();
    subject.markProgrammaticPop();

    // No overlay listener: the last one unmounted before back() ran.
    dispatchPopState();

    // The next event is the user, and must reach the overlay they reopened.
    expect(subject.isProgrammaticPop(new Event("popstate"))).toBe(false);
  });

  test("an overlay listener and the classifier agree on one event", () => {
    subject.resetOverlayEntries();
    subject.markProgrammaticPop();

    // Whoever asks first spends it; everyone else reads the same answer, so a
    // parent underneath cannot see the same event as a real back press.
    const event = new Event("popstate");
    expect(subject.isProgrammaticPop(event)).toBe(true);
    for (const listener of [...listeners]) listener(event);
    expect(subject.isProgrammaticPop(event)).toBe(true);

    expect(subject.isProgrammaticPop(new Event("popstate"))).toBe(false);
  });

  test("two overlays closing together spend one traversal each", () => {
    subject.resetOverlayEntries();
    subject.markProgrammaticPop();
    subject.markProgrammaticPop();

    dispatchPopState();
    dispatchPopState();

    expect(subject.isProgrammaticPop(new Event("popstate"))).toBe(false);
  });
});
