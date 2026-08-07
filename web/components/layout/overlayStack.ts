"use client";

import { useEffect, useRef, type RefObject } from "react";
import { focusableWithin, nextFocusIndex } from "./overlayFocus";

/**
 * One registry for every open overlay, and one place that routes input to them.
 *
 * The old shape gave every overlay its own document-level listener and asked it
 * to work out whether it should stay quiet. That is the wrong default: a
 * listener that exists will run, so correctness depended on each surface
 * remembering to check the stack, and every combination we had not thought of
 * was a bug. It produced the same failure five times, in five different
 * surfaces, each fix teaching one more component to stand down.
 *
 * So the layers are the state and the routing is central. A surface says it is
 * open and what it wants to do; it never listens. Escape, Tab containment, and
 * outside-dismiss go to the topmost layer and stop there. A new overlay cannot
 * reintroduce this class of bug by forgetting a guard, because there is no
 * guard for it to forget.
 *
 * This is the shape Radix and Headless UI settled on for the same problem.
 */

export type OverlayLayer = {
  id: string;
  /** The element focus is kept inside, and that outside-dismiss measures against. */
  containerRef: RefObject<HTMLElement | null>;
  /** Whether Tab is contained while this layer is topmost. */
  trapFocus: boolean;
  /** Escape, for the common case. */
  onEscape?: () => void;
  /**
   * Full keydown, for layers that own more than Escape.
   *
   * When present it replaces `onEscape`, and it still only runs while this
   * layer is topmost. Tab containment happens first so a layer cannot
   * accidentally take Tab away from itself.
   */
  onKeyDown?: (event: KeyboardEvent) => void;
  /** A press that landed outside the container, while this layer is topmost. */
  onOutsidePointerDown?: (event: PointerEvent) => void;
};

let layers: OverlayLayer[] = [];
let listening = false;

function topLayer(): OverlayLayer | null {
  return layers.length > 0 ? layers[layers.length - 1] : null;
}

function handleKeyDown(event: KeyboardEvent): void {
  const layer = topLayer();
  if (!layer) return;

  if (event.key === "Tab" && layer.trapFocus) {
    const elements = focusableWithin(layer.containerRef.current);
    if (elements.length > 0) {
      event.preventDefault();
      const index = nextFocusIndex({
        count: elements.length,
        currentIndex: elements.indexOf(document.activeElement as HTMLElement),
        direction: event.shiftKey ? "focus-previous" : "focus-next",
      });
      elements[index]?.focus();
      return;
    }
  }

  if (layer.onKeyDown) {
    layer.onKeyDown(event);
    return;
  }

  if (event.key === "Escape" && layer.onEscape) {
    event.preventDefault();
    event.stopPropagation();
    layer.onEscape();
  }
}

function handlePointerDown(event: PointerEvent): void {
  const layer = topLayer();
  if (!layer?.onOutsidePointerDown) return;
  const container = layer.containerRef.current;
  // `contains` rather than an instanceof check, which needs a DOM global to
  // exist and throws where one does not.
  if (container?.contains(event.target as Node)) return;
  layer.onOutsidePointerDown(event);
}

/** Listen only while something is open, so a closed app adds no handlers. */
function syncListeners(): void {
  const shouldListen = layers.length > 0;
  if (shouldListen === listening || typeof document === "undefined") return;
  listening = shouldListen;
  if (shouldListen) {
    document.addEventListener("keydown", handleKeyDown, true);
    document.addEventListener("pointerdown", handlePointerDown, true);
  } else {
    document.removeEventListener("keydown", handleKeyDown, true);
    document.removeEventListener("pointerdown", handlePointerDown, true);
  }
}

export function registerOverlayLayer(layer: OverlayLayer): void {
  layers = [...layers.filter((open) => open.id !== layer.id), layer];
  syncListeners();
}

/** Keeps a registered layer's callbacks current without reordering the stack. */
export function updateOverlayLayer(layer: OverlayLayer): void {
  if (!layers.some((open) => open.id === layer.id)) return;
  layers = layers.map((open) => (open.id === layer.id ? layer : open));
}

export function unregisterOverlayLayer(overlayId: string): void {
  layers = layers.filter((open) => open.id !== overlayId);
  syncListeners();
}

/** True when something opened on top of this overlay and should answer first. */
export function hasOverlayAbove(overlayId: string): boolean {
  const index = layers.findIndex((open) => open.id === overlayId);
  return index >= 0 && index < layers.length - 1;
}

export function isTopOverlay(overlayId: string): boolean {
  return topLayer()?.id === overlayId;
}

export function overlayStackIds(): readonly string[] {
  return layers.map((open) => open.id);
}

/** Test seam: reset between cases. */
export function resetOverlayStack(): void {
  layers = [];
  syncListeners();
}

/**
 * Registers a layer for as long as it is open.
 *
 * Callbacks are refreshed in place rather than by re-registering, because
 * re-registering would move the layer to the top of the stack on every render
 * and a parent would start outranking the dialog above it.
 */
export function useOverlayLayer({
  isOpen,
  overlayId,
  containerRef,
  trapFocus = false,
  onEscape,
  onKeyDown,
  onOutsidePointerDown,
}: {
  isOpen: boolean;
  overlayId: string;
  containerRef: RefObject<HTMLElement | null>;
  trapFocus?: boolean;
  onEscape?: () => void;
  onKeyDown?: (event: KeyboardEvent) => void;
  onOutsidePointerDown?: (event: PointerEvent) => void;
}): void {
  const handlers = useRef({ onEscape, onKeyDown, onOutsidePointerDown });
  // Refreshed after render rather than during it, and never as a dependency of
  // the registration below, which would resubscribe and reorder the stack.
  useEffect(() => {
    handlers.current = { onEscape, onKeyDown, onOutsidePointerDown };
  });

  useEffect(() => {
    if (!isOpen) return;
    const layer: OverlayLayer = {
      id: overlayId,
      containerRef,
      trapFocus,
      onEscape: (...args) => handlers.current.onEscape?.(...args),
      onKeyDown: onKeyDown
        ? (event) => handlers.current.onKeyDown?.(event)
        : undefined,
      onOutsidePointerDown: onOutsidePointerDown
        ? (event) => handlers.current.onOutsidePointerDown?.(event)
        : undefined,
    };
    registerOverlayLayer(layer);
    return () => unregisterOverlayLayer(overlayId);
    // Handler identity is held in a ref, so it must not resubscribe here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, overlayId, containerRef, trapFocus]);
}

/** Back-compat for callers that only need presence in the stack. */
export function useOverlayStackEntry(
  isOpen: boolean,
  overlayId: string,
  containerRef?: RefObject<HTMLElement | null>,
): void {
  const fallbackRef = useRef<HTMLElement | null>(null);
  useOverlayLayer({
    isOpen,
    overlayId,
    containerRef: containerRef ?? fallbackRef,
  });
}
