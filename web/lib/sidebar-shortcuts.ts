export function nextSidebarRecentsState(
  sidebarOpen: boolean,
  recentsExpanded: boolean,
) {
  if (sidebarOpen && recentsExpanded) {
    return { sidebarOpen: false, recentsExpanded: false };
  }

  return { sidebarOpen: true, recentsExpanded: true };
}
