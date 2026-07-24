type ChatToastProps = {
  message: string | null;
};

export default function ChatToast({ message }: ChatToastProps) {
  if (!message) return null;

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-24 z-[100] flex justify-center px-4">
      <div
        role="status"
        aria-live="polite"
        className="max-w-[min(720px,calc(100vw-2rem))] animate-in rounded-full border border-black/10 bg-white px-5 py-2.5 text-center text-[14px] font-medium text-black/80 shadow-[0_18px_60px_rgba(15,23,42,0.18)] duration-300 fade-in slide-in-from-bottom-2 dark:border-white/10 dark:bg-[#1f2225] dark:text-white/80 dark:shadow-[0_18px_60px_rgba(0,0,0,0.35)]"
      >
        {message}
      </div>
    </div>
  );
}
