export function dialogTabTarget<T>(
  focusable: T[],
  active: T | null,
  backwards: boolean,
): T | null {
  if (focusable.length === 0) return null;

  const activeIndex = active === null ? -1 : focusable.indexOf(active);
  if (activeIndex === -1) {
    return backwards ? focusable[focusable.length - 1] : focusable[0];
  }
  if (backwards && activeIndex === 0) {
    return focusable[focusable.length - 1];
  }
  if (!backwards && activeIndex === focusable.length - 1) {
    return focusable[0];
  }
  return null;
}
