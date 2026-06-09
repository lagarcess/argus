import type { SidebarMode } from "@/components/sidebar/ChatSidebar";

type SidebarNavigationState = {
  currentOpen: boolean;
  mode: SidebarMode;
};

export function sidebarOpenAfterTransientNavigation({
  currentOpen,
  mode,
}: SidebarNavigationState): boolean {
  if (mode === "expanded") {
    return currentOpen;
  }
  return false;
}
