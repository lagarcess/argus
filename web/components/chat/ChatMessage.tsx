"use client";

import { useState, useRef, useEffect } from "react";
import { ThumbsUp, ThumbsDown, MoreHorizontal, Copy, MessageSquareWarning } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTranslation } from "react-i18next";
import StrategyResultCard from "./StrategyResultCard";
import { Message } from "./types";
import { postFeedback } from "@/lib/argus-api";

type ChatMessageProps = {
  message: Message;
  onAction?: (value: string) => void;
  onFeedback?: (type: "bug" | "feature" | "general" | "rating", context: Record<string, any>, rating?: "positive" | "negative") => void;
  isLatest?: boolean;
  isStreaming?: boolean;
};

export default function ChatMessage({ message, onAction, onFeedback, isLatest, isStreaming }: ChatMessageProps) {
  const { t } = useTranslation();
  const isUser = message.role === "user";
  const [rating, setRating] = useState<"positive" | "negative" | null>(null);
  const [showOptions, setShowOptions] = useState(false);
  const [menuPosition, setMenuPosition] = useState<"top" | "bottom">("bottom");
  const optionsRef = useRef<HTMLDivElement>(null);

  const toggleOptions = (e: React.MouseEvent) => {
    if (!showOptions) {
      const buttonRect = e.currentTarget.getBoundingClientRect();
      // If the button is too close to the bottom of the screen (e.g. within 160px), map the popup upwards
      if (buttonRect.bottom + 160 > window.innerHeight) {
        setMenuPosition("top");
      } else {
        setMenuPosition("bottom");
      }
      setShowOptions(true);
    } else {
      setShowOptions(false);
    }
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (optionsRef.current && !optionsRef.current.contains(event.target as Node)) {
        setShowOptions(false);
      }
    }

    function handleScroll() {
      setShowOptions(false);
    }

    if (showOptions) {
      document.addEventListener("mousedown", handleClickOutside);
      // Use capture phase to ensure we catch the scroll event from the inner container natively
      window.addEventListener("scroll", handleScroll, true);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [showOptions]);

  const handleRating = (newRating: "positive" | "negative") => {
    if (rating === newRating) {
      setRating(null);
    } else {
      setRating(newRating);
      // First, post the basic rating
      postFeedback({
        type: "general",
        message: newRating === "positive" ? "Thumbs Up" : "Thumbs Down",
        context: { message_id: message.id, rating: newRating }
      });
      // Then, open the detailed feedback dialog
      onFeedback?.("rating", { message_id: message.id }, newRating);
    }
  };

  const getCopyText = () => {
    if (message.kind === "strategy_result" && message.result) {
      const rows = message.result.metrics.map((metric) => `${metric.label}: ${metric.value}`);
      const header = `${message.result.strategyName} (${message.result.period})`;
      const note = message.result.benchmarkNote ? `\n${message.result.benchmarkNote}` : "";
      return `${header}\n${rows.join("\n")}${note}`;
    }
    return message.content ?? "";
  };

  const getDisplayContent = () => {
    const content = message.content ?? "";
    if (content.startsWith("__ONBOARDING_SKIP__")) {
      return t("onboarding.skip", "Skip for now");
    }
    if (content.startsWith("__ONBOARDING_GOAL__:")) {
      const goal = content.split(":")[1];
      return t(`onboarding.goals.${goal}.title`, goal);
    }
    return content;
  };

  if (isUser) {
    return (
      <div className="flex w-full justify-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="max-w-[85%] bg-black/5 dark:bg-white/10 text-black dark:text-white px-5 py-3.5 rounded-[24px] rounded-br-sm text-[16px] leading-[1.5] tracking-[0.24px] font-normal shadow-sm">
          {getDisplayContent()}
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full justify-start animate-in fade-in slide-in-from-bottom-2 duration-300 group relative">
      {!isUser && !isStreaming && (
        <button
          onClick={() => {
            navigator.clipboard.writeText(getCopyText());
          }}
          className="absolute -left-10 top-1 opacity-0 group-hover:opacity-40 hover:!opacity-100 transition-opacity p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black dark:text-white"
          title={t('chat.copy_plaintext')}
        >
          <Copy className="w-4 h-4" />
        </button>
      )}
      <div className="flex flex-col max-w-[85%]">
        <div className="flex flex-col mt-1.5">
          {message.kind === "strategy_result" && message.result && !message.isLoadingResult ? (
            <div className="w-full max-w-[min(100%,660px)]">
              <StrategyResultCard result={message.result} />
            </div>
          ) : (
            <div className="text-black dark:text-white text-[16px] leading-[1.6] tracking-[0.24px] prose dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content ?? ""}
              </ReactMarkdown>
            </div>
          )}

          {isLatest && (
            <div className="flex items-start justify-between gap-4 mt-2">
              {message.actions && message.actions.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {message.actions.map((action) => (
                    <button
                      key={action.id}
                      type="button"
                      onClick={() => onAction?.(action.value)}
                      className="rounded-full border border-black/12 dark:border-white/12 px-3 py-1.5 text-[13px] font-medium tracking-tight text-black/80 dark:text-white/80 hover:bg-black/5 dark:hover:bg-white/6 transition-colors"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              ) : (
                <div />
              )}

              {/* Feedback Icon Row (Right-aligned) - Progressive Disclosure: Hide while streaming */}
              {!isStreaming && (
                <div className="relative flex items-center gap-1.5 opacity-50 hover:opacity-100 transition-opacity shrink-0" ref={optionsRef}>
                {(rating === null || rating === "positive") && (
                  <button
                    className={`p-1.5 rounded-full transition-all duration-200 group/thumb ${
                      rating === "positive"
                        ? "bg-black/5 dark:bg-white/10 text-black dark:text-white opacity-100 scale-110"
                        : "hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white"
                    }`}
                    title={t('chat.good_response')}
                    onClick={() => handleRating("positive")}
                  >
                    <ThumbsUp className={`w-3.5 h-3.5 ${rating === "positive" ? "fill-current" : ""}`} />
                  </button>
                )}
                {(rating === null || rating === "negative") && (
                  <button
                    className={`p-1.5 rounded-full transition-all duration-200 group/thumb ${
                      rating === "negative"
                        ? "bg-black/5 dark:bg-white/10 text-black dark:text-white opacity-100 scale-110"
                        : "hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white"
                    }`}
                    title={t('chat.poor_response')}
                    onClick={() => handleRating("negative")}
                  >
                    <ThumbsDown className={`w-3.5 h-3.5 ${rating === "negative" ? "fill-current" : ""}`} />
                  </button>
                )}
                <button
                  onClick={toggleOptions}
                  className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
                  title={t('chat.more_actions')}
                >
                  <MoreHorizontal className="w-3.5 h-3.5" />
                </button>

                {/* Popover Menu */}
                {showOptions && (
                  <div className={`absolute ${menuPosition === "bottom" ? "top-full mt-2" : "bottom-full mb-2"} right-0 w-[220px] bg-white dark:bg-[#1f2225] rounded-[24px] shadow-xl dark:shadow-black/50 border border-black/5 dark:border-white/5 py-2 z-50 animate-in fade-in zoom-in-95 duration-200`}>
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      onClick={() => { navigator.clipboard.writeText(getCopyText()); setShowOptions(false); }}
                    >
                      <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.copy_plaintext')}
                    </button>
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      onClick={() => { navigator.clipboard.writeText(message.id); setShowOptions(false); }}
                    >
                      <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.copy_id')}
                    </button>
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      onClick={() => { setShowOptions(false); onFeedback?.("bug", { message_id: message.id }); }}
                    >
                      <MessageSquareWarning className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.report_issue')}
                    </button>
                  </div>
                )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
