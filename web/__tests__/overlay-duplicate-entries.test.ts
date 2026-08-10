import { afterAll, beforeAll, beforeEach, describe, expect, test } from "bun:test";

/**
 * Nested overlays leave a duplicate history entry behind when one of them
 * navigates, and back looked like it had stopped working.
 *
 * Opening Omnisearch pushes a same-URL entry, opening a dossier inside it
 * pushes a second, and `Open conversation` writes the destination onto the top
 * one. The lower one is now a copy of the conversation the user started from,
 * sitting under the conversation they are reading. Back reaches the first copy
 * and stops; pressing again appears to do nothing, because the entry below is
 * the same URL again.
 *
 * The stack this file stands up is the point of the test. Asserting on the
 * module's own bookkeeping would pass whether or not the browser ever moved,
 * which is the mistake the first version of this made, so every case here
 * checks where the user actually ended up.
 */

type Listener = (event: Event) => void;

const ORIGIN = "https://app.test";
const SOURCE = `${ORIGIN}/chat?conversation=source`;
const DEST = `${ORIGIN}/chat?conversation=dest`;
const ELSEWHERE = `${ORIGIN}/chat?conversation=elsewhere`;

const listeners: Listener[] = [];
let stack: string[] = [];
let cursor = 0;
let subject: typeof import("../lib/overlay-history");

/** Where the user is right now, as `location.href` would report it. */
function currentHref(): string {
  return stack[cursor];
}

function dispatchPopState(): void {
  const event = new Event("popstate");
  for (const listener of [...listeners]) listener(event);
}

/**
 * A traversal, exactly as the browser performs one: move the cursor, then tell
 * everyone. Synchronous here, where real traversals are queued; the ordering
 * that depends on matters only against a real router, which is what the
 * Playwright pass covers.
 */
function traverse(steps: number): void {
  const next = Math.min(stack.length - 1, Math.max(0, cursor + steps));
  if (next === cursor) return;
  cursor = next;
  dispatchPopState();
}

/** A press of the hardware or browser back button. Nobody marks this. */
function userBack(): void {
  traverse(-1);
}

beforeAll(async () => {
  (globalThis as { window?: unknown }).window = {
    addEventListener: (type: string, listener: Listener) => {
      if (type === "popstate") listeners.push(listener);
    },
    removeEventListener: (type: string, listener: Listener) => {
      const at = listeners.indexOf(listener);
      if (at >= 0) listeners.splice(at, 1);
    },
    location: {
      get href() {
        return currentHref();
      },
      replace(value: string) {
        stack[cursor] = new URL(value, currentHref()).href;
      },
    },
    history: {
      get state() {
        return null;
      },
      back: () => traverse(-1),
      pushState: (_state: unknown, _title: string, url: string) => {
        stack = [...stack.slice(0, cursor + 1), url];
        cursor = stack.length - 1;
      },
      replaceState: (_state: unknown, _title: string, url: string) => {
        stack[cursor] = url;
      },
    },
  };
  subject = await import("../lib/overlay-history");
});

afterAll(() => {
  delete (globalThis as { window?: unknown }).window;
});

beforeEach(() => {
  subject.resetOverlayEntries();
  stack = [SOURCE];
  cursor = 0;
});

/** What the overlay hook does on open: take an id, push a copy of this URL. */
function openOverlay(overlayId: string): void {
  subject.recordOverlayEntry(overlayId);
  (globalThis as unknown as { window: Window }).window.history.pushState(
    null,
    "",
    currentHref(),
  );
}

/** What the routing does on the way out: spend the entries, write the URL. */
function navigateTo(href: string): void {
  subject.consumeOverlayEntriesForNavigation();
  (globalThis as unknown as { window: Window }).window.history.replaceState(
    null,
    "",
    href,
  );
}

describe("back after navigating out of nested overlays", () => {
  test("route navigation spends the overlay before its close callback", () => {
    openOverlay("settings");
    let closed = false;

    subject.navigateFromOverlay(DEST, () => {
      closed = true;
    });

    expect(closed).toBe(true);
    expect(currentHref()).toBe(DEST);
    expect(stack).toEqual([SOURCE, DEST]);
    expect(subject.claimOverlayEntry("settings")).toBe(false);
  });

  test("one press is one step, with no dead press in between", () => {
    openOverlay("palette");
    openOverlay("dossier");
    expect(stack).toEqual([SOURCE, SOURCE, SOURCE]);

    navigateTo(DEST);
    expect(currentHref()).toBe(DEST);

    userBack();
    expect(currentHref()).toBe(SOURCE);
    // The duplicate is what makes this the assertion that matters: landing on
    // SOURCE was already true before the fix, at cursor 1, with the real entry
    // still underneath. Only the cursor tells the two apart.
    expect(cursor).toBe(0);
  });

  test("a single overlay leaves nothing behind to skip", () => {
    openOverlay("palette");
    navigateTo(DEST);

    userBack();
    expect(currentHref()).toBe(SOURCE);
    expect(cursor).toBe(0);
  });

  test("the destination is not skipped once the user has moved on from it", () => {
    openOverlay("palette");
    openOverlay("dossier");
    navigateTo(DEST);

    // A later push, as any ordinary navigation from the destination would do.
    (globalThis as unknown as { window: Window }).window.history.pushState(
      null,
      "",
      ELSEWHERE,
    );

    userBack();
    // The duplicate is still owed, but this press did not land on one, and
    // spending it here would have thrown away the conversation behind it.
    expect(currentHref()).toBe(DEST);

    userBack();
    expect(currentHref()).toBe(SOURCE);
    expect(cursor).toBe(0);
  });

  test("a press belongs to an overlay that is still open", () => {
    openOverlay("palette");
    openOverlay("dossier");
    navigateTo(DEST);
    // Reopened over the destination, so it owns the next press and the debt
    // must wait rather than swallow it.
    openOverlay("reopened");

    userBack();
    expect(currentHref()).toBe(DEST);
    expect(subject.openOverlayEntries()).toEqual(["reopened"]);
  });
});
