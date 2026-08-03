import type { MutableRefObject } from "react";

export function messageElementRegistrar(
  refs: MutableRefObject<Map<string, HTMLDivElement>>,
  messageId: string,
): (element: HTMLDivElement | null) => void {
  return (element) => {
    if (element) {
      refs.current.set(messageId, element);
    } else {
      refs.current.delete(messageId);
    }
  };
}
