import { useCallback, useState } from "react";
import type { ChatToastVariant } from "./ChatToast";

type ChatToastState = {
  message: string;
  variant: ChatToastVariant;
} | null;

/** Owns the transient toast state; failures escalate via variant "error". */
export function useChatToast() {
  const [toast, setToast] = useState<ChatToastState>(null);
  const showToast = useCallback(
    (msg: string, variant: ChatToastVariant = "neutral") => {
      setToast({ message: msg, variant });
      setTimeout(() => setToast(null), 3000);
    },
    [],
  );
  return { toast, showToast };
}
