import { afterEach, describe, expect, test } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useResponsiveLayout } from "../components/layout/useResponsiveLayout";
import {
  BELOW_DESKTOP_QUERY, BELOW_TABLET_QUERY, DESKTOP_LAYOUT,
  responsiveLayoutSnapshot, subscribeResponsiveLayout,
} from "../lib/responsive-layout";

const originalWindow = globalThis.window;
afterEach(() => {
  if (originalWindow) globalThis.window = originalWindow;
  else Reflect.deleteProperty(globalThis, "window");
});

function mediaWindow() {
  const matches = new Map([[BELOW_TABLET_QUERY, true], [BELOW_DESKTOP_QUERY, true]]);
  const listeners = new Map<string, Set<() => void>>();
  globalThis.window = {
    matchMedia: (query: string) => ({
      get matches() { return matches.get(query) ?? false; },
      addEventListener: (_event: string, listener: () => void) => {
        if (!listeners.has(query)) listeners.set(query, new Set());
        listeners.get(query)!.add(listener);
      },
      removeEventListener: (_event: string, listener: () => void) => listeners.get(query)?.delete(listener),
    }),
  } as unknown as Window & typeof globalThis;
  return { matches, listeners };
}

describe("responsive layout external store", () => {
  test("server rendering uses the desktop hydration snapshot even with a phone client store", () => {
    mediaWindow();
    function Surface() {
      return createElement("span", null, useResponsiveLayout().isBelowDesktop ? "sheet" : "dialog");
    }
    expect(renderToStaticMarkup(createElement(Surface))).toBe("<span>dialog</span>");
    expect(responsiveLayoutSnapshot().isBelowDesktop).toBe(true);
  });

  test("a later client mount immediately sees phone width, without a desktop overlay first", () => {
    mediaWindow();
    expect(responsiveLayoutSnapshot()).toEqual({ isBelowTablet: true, isBelowDesktop: true });
    expect(responsiveLayoutSnapshot()).toBe(responsiveLayoutSnapshot());
    // SSR keeps the original desktop markup; client-only mounts read the store.
    Reflect.deleteProperty(globalThis, "window");
    expect(responsiveLayoutSnapshot()).toBe(DESKTOP_LAYOUT);
  });

  test("viewport changes notify readers and unchanged snapshots retain identity", () => {
    const media = mediaWindow();
    const before = responsiveLayoutSnapshot();
    let notifications = 0;
    const unsubscribe = subscribeResponsiveLayout(() => { notifications += 1; });
    media.matches.set(BELOW_TABLET_QUERY, false);
    media.listeners.get(BELOW_TABLET_QUERY)?.forEach((listener) => listener());
    expect(notifications).toBe(1);
    const tablet = responsiveLayoutSnapshot();
    expect(tablet).toEqual({ isBelowTablet: false, isBelowDesktop: true });
    expect(tablet).not.toBe(before);
    expect(responsiveLayoutSnapshot()).toBe(tablet);
    unsubscribe();
    expect([...media.listeners.values()].every((listeners) => listeners.size === 0)).toBe(true);
  });
});
