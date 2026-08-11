"use client";

import { useEffect, useState } from "react";
import {
  BELOW_DESKTOP_QUERY,
  BELOW_TABLET_QUERY,
  DESKTOP_LAYOUT,
  layoutsEqual,
  type ResponsiveLayout,
} from "@/lib/responsive-layout";

function readLayout(): ResponsiveLayout {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return DESKTOP_LAYOUT;
  }
  return {
    isBelowTablet: window.matchMedia(BELOW_TABLET_QUERY).matches,
    isBelowDesktop: window.matchMedia(BELOW_DESKTOP_QUERY).matches,
  };
}

/**
 * Current layout band by viewport width. Starts at the desktop band so server
 * markup and the first client paint agree, then corrects on mount.
 */
export function useResponsiveLayout(): ResponsiveLayout {
  const [layout, setLayout] = useState<ResponsiveLayout>(DESKTOP_LAYOUT);

  useEffect(() => {
    const sync = () =>
      setLayout((current) => {
        const next = readLayout();
        return layoutsEqual(current, next) ? current : next;
      });
    sync();
    const queries = [BELOW_TABLET_QUERY, BELOW_DESKTOP_QUERY].map((query) =>
      window.matchMedia(query),
    );
    queries.forEach((query) => query.addEventListener("change", sync));
    return () =>
      queries.forEach((query) => query.removeEventListener("change", sync));
  }, []);

  return layout;
}
