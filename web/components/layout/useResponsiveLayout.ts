"use client";

import { useSyncExternalStore } from "react";
import {
  DESKTOP_LAYOUT,
  responsiveLayoutSnapshot,
  subscribeResponsiveLayout,
  type ResponsiveLayout,
} from "@/lib/responsive-layout";

/**
 * SSR and hydration agree on desktop. Later client mounts read the actual band
 * immediately, so opening a phone panel never mounts a temporary desktop modal
 * that would register focus/history and then pop its entry during the swap.
 */
export function useResponsiveLayout(): ResponsiveLayout {
  return useSyncExternalStore(subscribeResponsiveLayout, responsiveLayoutSnapshot, () => DESKTOP_LAYOUT);
}
