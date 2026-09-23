import { useEffect, useRef, type DependencyList } from "react";

/** Focus a canonical recalled record only after its owner has rendered it. */
export function useRecordFocus<T extends HTMLElement = HTMLDivElement>(
  recordId: string | null,
  deps: DependencyList = [],
) {
  const rootRef = useRef<T>(null);
  const focused = useRef<string | null>(null);
  const selected = useRef<HTMLElement | null>(null);
  useEffect(() => {
    return () => {
      delete selected.current?.dataset.recordSelected;
      selected.current = null;
    };
  }, [recordId]);
  useEffect(() => {
    if (!recordId) {
      focused.current = null;
      return;
    }
    const target = Array.from(
      rootRef.current?.querySelectorAll<HTMLElement>("[data-record-id]") ?? [],
    ).find((element) => element.dataset.recordId === recordId);
    if (!target) return;
    if (selected.current !== target)
      delete selected.current?.dataset.recordSelected;
    selected.current = target;
    target.dataset.recordSelected = "true";
    if (focused.current === recordId) return;
    target.tabIndex = -1;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest", inline: "nearest" });
    focused.current = recordId;
  }, [recordId, ...deps]);
  return rootRef;
}
