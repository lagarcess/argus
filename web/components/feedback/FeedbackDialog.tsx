"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { X, Send, AlertCircle, Sparkles, MessageSquare, ThumbsUp, ThumbsDown } from "lucide-react";
import { postFeedback } from "@/lib/argus-api";

interface FeedbackDialogProps {
  isOpen: boolean;
  onClose: () => void;
  type: "bug" | "feature" | "general" | "rating";
  rating?: "positive" | "negative";
  context?: Record<string, any>;
}

export default function FeedbackDialog({ isOpen, onClose, type, rating, context }: FeedbackDialogProps) {
  const { t } = useTranslation();
  const [message, setMessage] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setMessage("");
      setSelectedTags([]);
      setIsSuccess(false);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // For non-rating feedback, message is required. For rating, tags or message is enough.
    const isRating = type === "rating";
    if (!isRating && !message.trim()) return;
    if (isRating && !message.trim() && selectedTags.length === 0) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await postFeedback({
        type: isRating ? "general" : type,
        message: message.trim() || (isRating ? `${rating} rating with tags` : ""),
        context: {
          ...context,
          rating,
          tags: selectedTags,
          url: typeof window !== "undefined" ? window.location.href : undefined,
          timestamp: new Date().toISOString(),
        },
      });
      setIsSuccess(true);
      setTimeout(() => onClose(), 2000);
    } catch (err) {
      setError(t("feedback.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const getTitle = () => {
    if (type === "rating") return t("feedback.title_rating");
    switch (type) {
      case "bug": return t("feedback.title_bug");
      case "feature": return t("feedback.title_feature");
      default: return t("feedback.title_general");
    }
  };

  const getIcon = () => {
    if (type === "rating") {
      return rating === "positive"
        ? <ThumbsUp className="w-5 h-5 text-green-500" />
        : <ThumbsDown className="w-5 h-5 text-red-500" />;
    }
    switch (type) {
      case "bug": return <AlertCircle className="w-5 h-5 text-red-500" />;
      case "feature": return <Sparkles className="w-5 h-5 text-amber-500" />;
      default: return <MessageSquare className="w-5 h-5 text-blue-500" />;
    }
  };

  const toggleTag = (tagKey: string) => {
    setSelectedTags(prev =>
      prev.includes(tagKey)
        ? prev.filter(t => t !== tagKey)
        : [...prev, tagKey]
    );
  };

  const tags = rating === "positive"
    ? [
        { key: "accurate", label: t("feedback.tags.positive.accurate") },
        { key: "exactly", label: t("feedback.tags.positive.exactly") },
        { key: "fast", label: t("feedback.tags.positive.fast") },
        { key: "style", label: t("feedback.tags.positive.style") },
        { key: "helpful", label: t("feedback.tags.positive.helpful") },
        { key: "other", label: t("feedback.tags.positive.other") },
      ]
    : [
        { key: "incorrect", label: t("feedback.tags.negative.incorrect") },
        { key: "not_what_asked", label: t("feedback.tags.negative.not_what_asked") },
        { key: "slow", label: t("feedback.tags.negative.slow") },
        { key: "style", label: t("feedback.tags.negative.style") },
        { key: "safety", label: t("feedback.tags.negative.safety") },
        { key: "other", label: t("feedback.tags.negative.other") },
      ];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/20 dark:bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative w-full max-w-lg bg-[#f5f5f5] dark:bg-[#1c1f24] border border-black/5 dark:border-white/10 rounded-[32px] overflow-hidden animate-in zoom-in-95 fade-in duration-300">
        <div className="p-6 sm:p-8">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-2xl bg-black/5 dark:bg-white/5">
                {getIcon()}
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-[var(--color-argus-fg)]">
                {getTitle()}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <X className="w-5 h-5 opacity-40" />
            </button>
          </div>

          {isSuccess ? (
            <div className="py-12 text-center animate-in zoom-in-95 duration-300">
              <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                <Send className="w-10 h-10 text-green-500" />
              </div>
              <p className="text-xl font-bold text-[var(--color-argus-fg)]">
                {t("feedback.success")}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {type === "rating" && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {tags.map((tag) => (
                    <button
                      key={tag.key}
                      type="button"
                      onClick={() => toggleTag(tag.key)}
                      className={`px-4 py-2 rounded-full text-[14px] font-medium border transition-all ${ selectedTags.includes(tag.key) ? "bg-black dark:bg-white text-white dark:text-black border-transparent" : "bg-white/50 dark:bg-white/5 border-black/5 dark:border-white/10 text-black/60 dark:text-white/60 hover:border-black/20 dark:hover:border-white/30" }`}
                    >
                      {tag.label}
                    </button>
                  ))}
                </div>
              )}

              <div className="space-y-2">
                <div className="relative">
                  <textarea
                    autoFocus={type !== "rating"}
                    value={message}
                    onChange={(e) => setMessage(e.target.value.slice(0, 500))}
                    placeholder={type === "rating" ? t("feedback.placeholder_details") : t("feedback.placeholder")}
                    className="w-full min-h-[140px] p-4 pb-8 bg-white/80 dark:bg-black/40 border border-black/5 dark:border-white/5 rounded-2xl outline-none focus:ring-2 focus:ring-black/5 dark:focus:ring-white/5 transition-all resize-none text-[var(--color-argus-fg)] placeholder:opacity-30"
                  />
                  <div className="absolute bottom-3 right-4 text-[11px] font-medium text-black/20 dark:text-white/20 tabular-nums">
                    {message.length}/500
                  </div>
                </div>

                {type === "rating" && (
                  <p className="px-1 text-[13px] text-black/40 dark:text-white/40 leading-relaxed">
                    {t("feedback.footer_note")}{" "}
                    <button type="button" className="underline hover:text-black dark:hover:text-white transition-colors">
                      {t("landing.privacy")}
                    </button>
                  </p>
                )}
              </div>

              {error && (
                <p className="text-sm text-red-500 animate-in fade-in slide-in-from-top-1">
                  {error}
                </p>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-6 py-3.5 text-[15px] font-semibold rounded-2xl hover:bg-black/5 dark:hover:bg-white/5 transition-all active:scale-[0.98]"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || (!message.trim() && (type !== "rating" || selectedTags.length === 0))}
                  className="px-8 py-3.5 bg-black dark:bg-white text-white dark:text-black text-[15px] font-bold rounded-2xl hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-30 disabled:pointer-events-none flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      {t("common.submit")}
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
