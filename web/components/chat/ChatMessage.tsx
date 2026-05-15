"use client";

import { useState, useRef, useEffect } from "react";
import { ThumbsUp, ThumbsDown, MoreHorizontal, Copy, MessageSquareWarning } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTranslation } from "react-i18next";
import StrategyResultCard from "./StrategyResultCard";
import StrategyConfirmationCard from "./StrategyConfirmationCard";
import { type ChatActionOption, type ChatMention, Message } from "./types";
import { postFeedback } from "@/lib/argus-api";

type ChatMessageProps = {
  message: Message;
  onAction?: (action: ChatActionOption) => void;
  onFeedback?: (type: "bug" | "feature" | "general" | "rating", context: Record<string, unknown>, rating?: "positive" | "negative") => void;
  isLatest?: boolean;
  isStreaming?: boolean;
};

export default function ChatMessage({ message, onAction, onFeedback, isLatest, isStreaming }: ChatMessageProps) {
  const { t } = useTranslation();
  const isUser = message.role === "user";
  const [rating, setRating] = useState<"positive" | "negative" | null>(null);
  const [showOptions, setShowOptions] = useState(false);
  const [menuPosition, setMenuPosition] = useState<"top" | "bottom">("bottom");
  const [copyFeedback, setCopyFeedback] = useState<"success" | "failed" | null>(null);
  const optionsRef = useRef<HTMLDivElement>(null);
  const copyFeedbackTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  useEffect(() => {
    return () => {
      if (copyFeedbackTimeoutRef.current) {
        clearTimeout(copyFeedbackTimeoutRef.current);
      }
    };
  }, []);

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
    if (message.copyText) {
      return message.copyText;
    }
    if (message.kind === "strategy_result" && message.result) {
      if (message.result.copyText) {
        return message.result.copyText;
      }
      const rows = message.result.metrics.map((metric) => `${metric.label}: ${metric.value}`);
      const symbols = message.result.symbols?.length
        ? `Symbols: ${message.result.symbols.join(", ")}`
        : null;
      const assumptions = message.result.assumptions?.length
        ? `Assumptions: ${message.result.assumptions.join(" • ")}`
        : null;
      return [
        message.result.strategyName,
        symbols,
        `Period: ${message.result.period}`,
        rows.join("\n"),
        message.result.benchmarkNote,
        assumptions,
        message.content ? `Assistant explanation:\n${message.content}` : null,
      ].filter(Boolean).join("\n");
    }
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      if (message.confirmation.copyText) {
        return message.confirmation.copyText;
      }
      const rows = message.confirmation.rows.map((row) => `${row.label}: ${row.value}`);
      const assumptions = message.confirmation.assumptions?.length
        ? `Assumptions: ${message.confirmation.assumptions.join(" • ")}`
        : null;
      return [
        message.confirmation.title,
        message.confirmation.summary,
        rows.join("\n"),
        assumptions,
      ].filter(Boolean).join("\n");
    }
    return message.content ?? "";
  };

  const handleCopy = async (text = getCopyText()) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback("success");
    } catch {
      setCopyFeedback("failed");
    }
    if (copyFeedbackTimeoutRef.current) {
      clearTimeout(copyFeedbackTimeoutRef.current);
    }
    copyFeedbackTimeoutRef.current = setTimeout(() => {
      setCopyFeedback(null);
      copyFeedbackTimeoutRef.current = null;
    }, 2000);
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

  if (isUser && message.kind === "action") {
    return (
      <div className="flex w-full justify-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="max-w-[85%] rounded-full border border-black/10 bg-black/[0.03] px-4 py-2.5 text-[14px] font-medium leading-[1.45] text-black/75 dark:border-white/12 dark:bg-white/[0.06] dark:text-white/75">
          {message.selectedAction?.label ?? getDisplayContent()}
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="flex w-full justify-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="max-w-[85%] bg-black/5 dark:bg-white/10 text-black dark:text-white px-5 py-3.5 rounded-[24px] rounded-br-sm text-[16px] leading-[1.5] tracking-[0.24px] font-normal">
          <UserMessageContent content={getDisplayContent()} mentions={message.mentions ?? []} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full justify-start animate-in fade-in slide-in-from-bottom-2 duration-300 group relative">
      {!isUser && !isStreaming && !copyFeedback && (
        <button
          onClick={() => {
            void handleCopy();
          }}
          className="absolute -left-10 top-1 opacity-0 group-hover:opacity-40 hover:!opacity-100 transition-opacity p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black dark:text-white"
          title={t('chat.copy_plaintext')}
        >
          <Copy className="w-4 h-4" />
        </button>
      )}
      {copyFeedback && (
        <span
          role="status"
          aria-live="polite"
          className="absolute -left-12 top-10 rounded-full border border-black/10 bg-white px-2.5 py-1 text-[11px] font-medium text-black/70 dark:border-white/10 dark:bg-[#1f2225] dark:text-white/70"
        >
          {t(copyFeedback === "success" ? "chat.copy_success" : "chat.copy_failed")}
        </span>
      )}
      <div className="flex flex-col max-w-[85%]">
        <div className="flex flex-col mt-1.5">
          {message.kind === "strategy_result" && message.result && !message.isLoadingResult ? (
            <div className="flex w-full max-w-[min(100%,660px)] flex-col gap-4">
              <StrategyResultCard result={message.result} onAction={onAction} />
              {message.content && (
                <ResultReadout content={message.content} />
              )}
            </div>
          ) : message.kind === "strategy_confirmation" && message.confirmation ? (
            <div className="w-full max-w-[min(100%,660px)]">
              <StrategyConfirmationCard confirmation={message.confirmation} onAction={onAction} />
            </div>
          ) : message.contentPresentation === "result_breakdown" ? (
            <ResultBreakdown content={message.content ?? ""} />
          ) : (
            <div className="text-black dark:text-white text-[16px] leading-[1.6] tracking-[0.24px] prose dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content ?? ""}
              </ReactMarkdown>
            </div>
          )}

          {isLatest && message.kind === "text" && (
            <div className="flex items-start justify-between gap-4 mt-2">
              {message.actions && message.actions.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {message.actions.map((action) => (
                    <button
                      key={action.id ?? action.type ?? action.label}
                      type="button"
                      onClick={() => onAction?.(action)}
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
                    className={`p-1.5 rounded-full transition-all duration-200 group/thumb ${ rating === "positive" ? "bg-black/5 dark:bg-white/10 text-black dark:text-white opacity-100 scale-110" : "hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white" }`}
                    title={t('chat.good_response')}
                    onClick={() => handleRating("positive")}
                  >
                    <ThumbsUp className={`w-3.5 h-3.5 ${rating === "positive" ? "fill-current" : ""}`} />
                  </button>
                )}
                {(rating === null || rating === "negative") && (
                  <button
                    className={`p-1.5 rounded-full transition-all duration-200 group/thumb ${ rating === "negative" ? "bg-black/5 dark:bg-white/10 text-black dark:text-white opacity-100 scale-110" : "hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white" }`}
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
                  <div className={`absolute ${menuPosition === "bottom" ? "top-full mt-2" : "bottom-full mb-2"} right-0 w-[220px] bg-white dark:bg-[#1f2225] rounded-[24px] border border-black/5 dark:border-white/5 py-2 z-50 animate-in fade-in zoom-in-95 duration-200`}>
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      onClick={() => { void handleCopy(); setShowOptions(false); }}
                    >
                      <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.copy_plaintext')}
                    </button>
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      onClick={() => { void handleCopy(message.id); setShowOptions(false); }}
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

function ResultReadout({ content }: { content: string }) {
  return (
    <section
      className="argus-result-readout prose dark:prose-invert max-w-none"
      aria-label="Result readout"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </section>
  );
}

function ResultBreakdown({ content }: { content: string }) {
  return (
    <section
      className="argus-result-breakdown prose dark:prose-invert max-w-none"
      aria-label="Result breakdown"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </section>
  );
}

function UserMessageContent({ content, mentions }: { content: string; mentions: ChatMention[] }) {
  if (mentions.length === 0) return <>{content}</>;

  const pieces: Array<string | ChatMention> = [];
  let cursor = 0;
  const remainingMentions = [...mentions];

  while (cursor < content.length) {
    let nextMatch:
      | {
          index: number;
          mention: ChatMention;
          text: string;
          mentionIndex: number;
        }
      | null = null;

    for (let mentionIndex = 0; mentionIndex < remainingMentions.length; mentionIndex++) {
      const mention = remainingMentions[mentionIndex];
      const candidates = [mention.insert_text, mention.symbol ?? "", mention.label]
        .filter(Boolean)
        .sort((a, b) => b.length - a.length);
      for (const candidate of candidates) {
        const index = content.indexOf(candidate, cursor);
        if (index < 0) continue;
        if (nextMatch === null || index < nextMatch.index) {
          nextMatch = { index, mention, text: candidate, mentionIndex };
        }
      }
    }

    if (nextMatch === null) {
      pieces.push(content.slice(cursor));
      break;
    }

    if (nextMatch.index > cursor) {
      pieces.push(content.slice(cursor, nextMatch.index));
    }
    pieces.push(nextMatch.mention);
    cursor = nextMatch.index + nextMatch.text.length;
    remainingMentions.splice(nextMatch.mentionIndex, 1);
  }

  return (
    <>
      {pieces.map((piece, index) =>
        typeof piece === "string" ? (
          <span key={`text-${index}`}>{piece}</span>
        ) : (
          <MentionText key={`${piece.id}-${index}`} mention={piece} />
        ),
      )}
    </>
  );
}

function MentionText({ mention }: { mention: ChatMention }) {
  const label = mention.type === "asset" ? mention.insert_text : mention.label;
  const color =
    mention.type === "asset"
      ? "text-[#c2a44d]"
      : "text-[#494fdf] dark:text-[#8f93ff]";

  return (
    <span
      className={`mx-0.5 inline-flex select-none items-baseline rounded-sm px-0.5 font-semibold ${color}`}
      title={mention.description ?? mention.label}
    >
      {label}
    </span>
  );
}
