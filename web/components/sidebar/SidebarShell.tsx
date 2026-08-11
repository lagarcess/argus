"use client";

import type { ReactNode } from "react";
import SidebarDrawer from "./SidebarDrawer";

/**
 * Places the sidebar for the current width band (spec section 2). Above the
 * mobile threshold it stays an inline rail; below it there is no rail at all,
 * only an off-canvas drawer that the top bar's trigger opens.
 */
export default function SidebarShell({
  isBelowTablet,
  isDrawerOpen,
  onCloseDrawer,
  label,
  children,
}: {
  isBelowTablet: boolean;
  isDrawerOpen: boolean;
  onCloseDrawer: () => void;
  label: string;
  children: ReactNode;
}) {
  if (!isBelowTablet) return <>{children}</>;
  return (
    <SidebarDrawer isOpen={isDrawerOpen} onClose={onCloseDrawer} label={label}>
      {children}
    </SidebarDrawer>
  );
}
