import { MessageSquareWarning } from "lucide-react";

export type ChatToastVariant = "neutral" | "error";

export type ChatToastAction = {
  label: string;
  onPress: () => void;
};

type ChatToastProps = {
  message: string | null;
  variant?: ChatToastVariant;
  action?: ChatToastAction;
};

export default function ChatToast({
  message,
  variant = "neutral",
  action,
}: ChatToastProps) {
  if (!message && !action) return null;

  const isError = variant === "error";
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-24 z-[100] flex justify-center px-4">
      <div
        role={isError ? "alert" : "status"}
        aria-live={isError ? "assertive" : "polite"}
        className={`pointer-events-auto flex max-w-[min(720px,calc(100vw-2rem))] items-center gap-3 animate-in rounded-full border px-5 py-2.5 text-center text-[14px] font-medium shadow-[0_18px_60px_rgba(15,23,42,0.18)] duration-300 fade-in slide-in-from-bottom-2 dark:shadow-[0_18px_60px_rgba(0,0,0,0.35)] ${
          isError
            ? "border-[#b3593f]/30 bg-white text-[#9c4a33] dark:border-[#e08d70]/30 dark:bg-[#1f2225] dark:text-[#e5a48b]"
            : "border-black/10 bg-white text-black/80 dark:border-white/10 dark:bg-[#1f2225] dark:text-white/80"
        }`}
      >
        {isError ? (
          <MessageSquareWarning
            className="me-2 inline-block h-4 w-4 shrink-0 align-[-3px]"
            aria-hidden="true"
          />
        ) : null}
        {message ? <span>{message}</span> : null}
        {action ? (
          <button
            type="button"
            onClick={action.onPress}
            className="min-h-8 shrink-0 rounded-full px-2 font-semibold text-[#5ba897] transition-colors hover:text-[#4a8f80] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5ba897]/40"
          >
            {action.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}
