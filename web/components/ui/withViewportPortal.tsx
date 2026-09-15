"use client";

import { useSyncExternalStore, type ComponentType } from "react";
import { createPortal } from "react-dom";

const subscribe = () => () => {};
const clientSnapshot = () => true;
const serverSnapshot = () => false;

/**
 * Viewport overlays belong to the body, outside transformed or clipped owners.
 * Mount the whole surface here, including its focus and layer hooks, so those
 * hooks never register before the portal exists. The server and first hydration
 * render are empty; an initially open overlay mounts safely after hydration.
 */
export function withViewportPortal<Props extends object>(Surface: ComponentType<Props>) {
  function ViewportOverlay(props: Props) {
    const mounted = useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
    return mounted ? createPortal(<Surface {...props} />, document.body) : null;
  }
  ViewportOverlay.displayName = `ViewportOverlay(${Surface.displayName ?? Surface.name ?? "Surface"})`;
  return ViewportOverlay;
}
