import { useCallback, useRef, useState } from "react";
import type { ChatToastAction, ChatToastVariant } from "./ChatToast";

type ChatToastState = {
  message: string;
  variant: ChatToastVariant;
  action?: ChatToastAction;
} | null;

type ShowToastOptions = {
  action?: ChatToastAction;
  durationMs?: number;
};

/** Owns the transient toast state; failures escalate via variant "error".
 * One toast at a time: a new call replaces the current one instead of
 * stacking, and replacing also resets the dismiss timer. */
export function useChatToast() {
  const [toast, setToast] = useState<ChatToastState>(null);
  const timerRef = useRef<number | null>(null);
  const hideToast = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setToast(null);
  }, []);
  const showToast = useCallback(
    (
      msg: string,
      variant: ChatToastVariant = "neutral",
      options: ShowToastOptions = {},
    ) => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
      setToast({ message: msg, variant, action: options.action });
      timerRef.current = window.setTimeout(
        () => setToast(null),
        options.durationMs ?? 3000,
      );
    },
    [],
  );
  return { toast, showToast, hideToast };
}
