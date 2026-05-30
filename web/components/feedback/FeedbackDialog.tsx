"use client";

import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import {
  AlertCircle,
  Bug,
  Check,
  ChevronDown,
  Lightbulb,
  MessageCircle,
  Paperclip,
  Send,
  X,
} from "lucide-react";
import { postFeedback } from "@/lib/argus-api";

type FeedbackType = "bug" | "feature" | "general" | "rating";

interface FeedbackDialogProps {
  isOpen: boolean;
  onClose: () => void;
  type: FeedbackType;
  rating?: "positive" | "negative";
  context?: Record<string, unknown>;
}

type FeedbackTypeOption = {
  value: Exclude<FeedbackType, "rating">;
  label: string;
  icon: ReactNode;
};

export default function FeedbackDialog({
  isOpen,
  onClose,
  type: initialType,
  rating,
  context,
}: FeedbackDialogProps) {
  const { t } = useTranslation();
  const [type, setType] = useState<FeedbackType>(initialType);
  const [message, setMessage] = useState("");
  const [bugTitle, setBugTitle] = useState("");
  const [steps, setSteps] = useState("");
  const [expected, setExpected] = useState("");
  const [actual, setActual] = useState("");
  const [consent, setConsent] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    setType(initialType);
    setMessage("");
    setBugTitle("");
    setSteps("");
    setExpected("");
    setActual("");
    setConsent(false);
    setFiles([]);
    setSelectedTags([]);
    setIsSubmitting(false);
    setIsSuccess(false);
    setError(null);
    setDropdownOpen(false);
  }, [initialType, isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isRating = type === "rating";
  const isBug = type === "bug";
  const isFeature = type === "feature";
  const hasConversationContext =
    typeof context?.conversation_id === "string" && context.conversation_id.length > 0;

  const typeOptions: FeedbackTypeOption[] = [
    {
      value: "general",
      label: t("feedback.type.general", "General Feedback"),
      icon: <MessageCircle className="h-4 w-4" />,
    },
    {
      value: "bug",
      label: t("feedback.type.bug", "Report a Bug"),
      icon: <Bug className="h-4 w-4" />,
    },
    {
      value: "feature",
      label: t("feedback.type.feature", "Request a Feature"),
      icon: <Lightbulb className="h-4 w-4" />,
    },
  ];

  const currentType =
    typeOptions.find((option) => option.value === type) ?? typeOptions[0];

  const ratingTags =
    rating === "positive"
      ? [
          { key: "accurate", label: t("feedback.tags.positive.accurate", "Accurate") },
          { key: "exactly", label: t("feedback.tags.positive.exactly", "Exactly what I needed") },
          { key: "fast", label: t("feedback.tags.positive.fast", "Fast") },
          { key: "style", label: t("feedback.tags.positive.style", "Good format") },
          { key: "helpful", label: t("feedback.tags.positive.helpful", "Helpful") },
          { key: "other", label: t("feedback.tags.positive.other", "Other") },
        ]
      : [
          { key: "incorrect", label: t("feedback.tags.negative.incorrect", "Incorrect") },
          { key: "not_what_asked", label: t("feedback.tags.negative.not_what_asked", "Not what I asked") },
          { key: "slow", label: t("feedback.tags.negative.slow", "Too slow") },
          { key: "style", label: t("feedback.tags.negative.style", "Bad format") },
          { key: "safety", label: t("feedback.tags.negative.safety", "Safety concern") },
          { key: "other", label: t("feedback.tags.negative.other", "Other") },
        ];

  const canSubmit = () => {
    if (isRating) return selectedTags.length > 0 || message.trim().length > 0;
    if (!consent) return false;
    if (isBug) return bugTitle.trim().length > 0 && steps.trim().length > 0;
    return message.trim().length > 0;
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles) return;

    const nextFiles = Array.from(selectedFiles);
    if (files.length + nextFiles.length > 5) {
      setError(t("feedback.max_files", "Maximum 5 files allowed."));
      return;
    }

    setFiles((current) => [...current, ...nextFiles].slice(0, 5));
    setError(null);
    event.target.value = "";
  };

  const removeFile = (index: number) => {
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index));
  };

  const toggleTag = (tagKey: string) => {
    setSelectedTags((current) =>
      current.includes(tagKey)
        ? current.filter((existing) => existing !== tagKey)
        : [...current, tagKey],
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit()) return;

    setIsSubmitting(true);
    setError(null);

    const finalMessage = isBug
      ? [
          `${t("feedback.bug.message_title", "Title")}: ${bugTitle.trim()}`,
          `${t("feedback.bug.message_steps", "Steps to reproduce")}:\n${steps.trim()}`,
          `${t("feedback.bug.message_expected", "Expected outcome")}:\n${expected.trim()}`,
          `${t("feedback.bug.message_actual", "Actual outcome")}:\n${actual.trim()}`,
        ].join("\n\n")
      : message.trim();

    try {
      await postFeedback({
        type: isRating ? "general" : type,
        message:
          finalMessage ||
          (isRating ? t("feedback.rating_message_fallback", "{{rating}} rating with tags", { rating }) : ""),
        context: {
          ...context,
          rating,
          tags: selectedTags,
          url: typeof window !== "undefined" ? window.location.href : undefined,
          timestamp: new Date().toISOString(),
          hasAttachments: files.length > 0,
          attachmentCount: files.length,
        },
      });
      setIsSuccess(true);
      setTimeout(() => onClose(), 2000);
    } catch {
      setError(t("feedback.error", "We could not submit that yet. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const title = "Provide feedback";
  const displayTitle = t("feedback.title", title);

  const subheading = isRating
    ? rating === "positive"
      ? t("feedback.subheading.positive", "What worked well in this response?")
      : t("feedback.subheading.negative", "What should be improved in this response?")
    : type === "bug"
      ? t("feedback.subheading.bug", "File a bug report.")
      : type === "feature"
        ? t("feedback.subheading.feature", "Request a feature for Argus.")
        : t("feedback.subheading.general", "Share feedback about your Argus experience.");

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/20 backdrop-blur-sm dark:bg-black/60"
        onClick={onClose}
        aria-label="Close feedback"
      />

      <div className="relative flex max-h-[90vh] w-full max-w-[600px] flex-col overflow-hidden rounded-[28px] border border-black/10 bg-[#f5f5f5] dark:border-white/10 dark:bg-[#1c1f24]">
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-black/5 px-6 py-6 dark:border-white/5 sm:px-8">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2 text-black/45 dark:text-white/45">
              <MessageCircle className="h-4 w-4" />
              <span className="font-display text-[11px] font-semibold uppercase tracking-wider">
                {t("feedback.eyebrow", "Feedback")}
              </span>
            </div>
            <h2 className="font-display text-[22px] font-semibold tracking-tight text-black dark:text-white">
              {displayTitle}
            </h2>
            <p className="mt-1 text-[13px] leading-relaxed text-black/50 dark:text-white/50">
              {subheading}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-black/40 transition-colors hover:bg-black/5 hover:text-black dark:text-white/40 dark:hover:bg-white/5 dark:hover:text-white"
            aria-label="Close feedback"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="argus-thin-scrollbar flex-1 overflow-y-auto p-6 sm:p-8">
          {isSuccess ? (
            <div className="py-12 text-center">
              <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-[#5ba897]/10">
                <Send className="h-7 w-7 text-[#5ba897]" />
              </div>
              <p className="font-display text-[18px] font-medium text-black dark:text-white">
                {t("feedback.success_detail", "Feedback submitted.")}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-6">
              {!isRating && (
                <div className="relative">
                  <label className="mb-2 block text-[13px] font-medium uppercase tracking-wide text-black/60 dark:text-white/60">
                    {t("feedback.type_label", "Feedback type")}
                  </label>
                  <button
                    type="button"
                    onClick={() => setDropdownOpen((open) => !open)}
                    className="flex w-full items-center justify-between rounded-xl border border-black/10 bg-white px-4 py-3 text-[14px] text-black transition-colors hover:border-black/20 dark:border-white/10 dark:bg-[#25282d] dark:text-white dark:hover:border-white/20"
                  >
                    <span className="flex items-center gap-3">
                      <span className="text-black/40 dark:text-white/40">
                        {currentType.icon}
                      </span>
                      <span className="font-medium">{currentType.label}</span>
                    </span>
                    <ChevronDown
                      className={`h-4 w-4 text-black/40 transition-transform dark:text-white/40 ${
                        dropdownOpen ? "rotate-180" : ""
                      }`}
                    />
                  </button>

                  {dropdownOpen && (
                    <div className="absolute left-0 top-[calc(100%+8px)] z-10 w-full overflow-hidden rounded-xl border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#25282d]">
                      {typeOptions.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => {
                            setType(option.value);
                            setDropdownOpen(false);
                          }}
                          className="flex w-full items-center gap-3 px-4 py-3 text-left text-[14px] text-black transition-colors hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
                        >
                          <span className="text-black/40 dark:text-white/40">
                            {option.icon}
                          </span>
                          <span className="flex-1 font-medium">{option.label}</span>
                          {type === option.value && (
                            <Check className="h-4 w-4 text-[#4f55f1]" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {isBug && !isRating ? (
                <>
                  <div>
                    <label className="mb-2 block text-[13px] font-medium text-black/60 dark:text-white/60">
                      {t("feedback.bug.title_field", "Title")} *
                    </label>
                    <input
                      value={bugTitle}
                      onChange={(event) => setBugTitle(event.target.value.slice(0, 100))}
                      placeholder={t("feedback.bug.title_placeholder", "Brief description of the issue")}
                      className="w-full rounded-xl border border-black/10 bg-white px-4 py-3 text-[14px] text-black outline-none transition-colors placeholder:text-black/30 focus:border-[#4f55f1] dark:border-white/10 dark:bg-[#25282d] dark:text-white dark:placeholder:text-white/30"
                    />
                    <div className="mt-1 text-right text-[11px] text-black/30 dark:text-white/30">
                      {bugTitle.length}/100
                    </div>
                  </div>

                  <div>
                    <label className="mb-2 block text-[13px] font-medium text-black/60 dark:text-white/60">
                      {t("feedback.bug.steps_field", "Steps to reproduce")} *
                    </label>
                    <textarea
                      value={steps}
                      onChange={(event) => setSteps(event.target.value.slice(0, 1000))}
                      placeholder={t(
                        "feedback.bug.steps_placeholder",
                        "1. Go to [Page/View]\n2. Click on [Button/Action]\n3. See [Error/Behavior]",
                      )}
                      className="min-h-[100px] w-full resize-y rounded-xl border border-black/10 bg-white px-4 py-3 text-[14px] text-black outline-none transition-colors placeholder:text-black/30 focus:border-[#4f55f1] dark:border-white/10 dark:bg-[#25282d] dark:text-white dark:placeholder:text-white/30"
                    />
                    <div className="mt-1 text-right text-[11px] text-black/30 dark:text-white/30">
                      {steps.length}/1000
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-[13px] font-medium text-black/60 dark:text-white/60">
                        {t("feedback.bug.expected_field", "Expected outcome")}
                      </label>
                      <textarea
                        value={expected}
                        onChange={(event) => setExpected(event.target.value.slice(0, 500))}
                        className="min-h-[80px] w-full resize-none rounded-xl border border-black/10 bg-white px-4 py-3 text-[14px] text-black outline-none transition-colors focus:border-[#4f55f1] dark:border-white/10 dark:bg-[#25282d] dark:text-white"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-[13px] font-medium text-black/60 dark:text-white/60">
                        {t("feedback.bug.actual_field", "Actual outcome")}
                      </label>
                      <textarea
                        value={actual}
                        onChange={(event) => setActual(event.target.value.slice(0, 500))}
                        className="min-h-[80px] w-full resize-none rounded-xl border border-black/10 bg-white px-4 py-3 text-[14px] text-black outline-none transition-colors focus:border-[#4f55f1] dark:border-white/10 dark:bg-[#25282d] dark:text-white"
                      />
                    </div>
                  </div>
                </>
              ) : (
                <div className={isRating ? "space-y-6" : ""}>
                  {isRating && (
                    <div>
                      <label className="mb-3 block text-[13px] font-medium text-black/60 dark:text-white/60">
                        {rating === "positive"
                          ? t("feedback.rating_positive_prompt", "What went well?")
                          : t("feedback.rating_negative_prompt", "What went wrong?")}
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {ratingTags.map((tag) => (
                          <button
                            key={tag.key}
                            type="button"
                            onClick={() => toggleTag(tag.key)}
                            className={`rounded-full border px-4 py-2 text-[13px] font-medium transition-all ${
                              selectedTags.includes(tag.key)
                                ? "border-transparent bg-black text-white dark:bg-white dark:text-black"
                                : "border-black/10 bg-white text-black/70 hover:border-black/20 dark:border-white/10 dark:bg-[#25282d] dark:text-white/70 dark:hover:border-white/30"
                            }`}
                          >
                            {tag.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="mb-2 block text-[13px] font-medium text-black/60 dark:text-white/60">
                      {isRating
                        ? t("feedback.additional_details", "Additional details")
                        : `${t("feedback.details", "Details")} *`}
                    </label>
                    <textarea
                      autoFocus={!isRating}
                      value={message}
                      onChange={(event) => setMessage(event.target.value.slice(0, 1000))}
                      placeholder={
                        isRating
                          ? t("feedback.rating_placeholder", "Tell us more about your experience...")
                          : t("feedback.details_placeholder", "What's on your mind?")
                      }
                      className="min-h-[140px] w-full resize-y rounded-xl border border-black/10 bg-white px-4 py-3 text-[14px] text-black outline-none transition-colors placeholder:text-black/30 focus:border-[#4f55f1] dark:border-white/10 dark:bg-[#25282d] dark:text-white dark:placeholder:text-white/30"
                    />
                    <div className="mt-1 text-right text-[11px] text-black/30 dark:text-white/30">
                      {message.length}/1000
                    </div>
                  </div>
                </div>
              )}

              {!isRating && (
                <div>
                  <label className="mb-2 block text-[13px] font-medium text-black/60 dark:text-white/60">
                    {t("feedback.attachments_with_count", "Attachments ({{count}}/5)", {
                      count: files.length,
                    })}
                  </label>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex w-full flex-col items-center justify-center rounded-xl border border-dashed border-black/20 p-6 text-center transition-colors hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/5"
                  >
                    <Paperclip className="mb-2 h-5 w-5 text-black/40 dark:text-white/40" />
                    <span className="text-[13px] text-black/60 dark:text-white/60">
                      {isFeature
                        ? t(
                            "feedback.attach_files_feature",
                            "Optional: add a screenshot, sketch, or example.",
                          )
                        : t("feedback.attach_files", "Click to attach files (max 5)")}
                    </span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                  />

                  {files.length > 0 && (
                    <div className="mt-3 flex flex-col gap-2">
                      {files.map((file, index) => (
                        <div
                          key={`${file.name}-${index}`}
                          className="flex items-center justify-between gap-3 rounded-lg border border-black/5 bg-white px-3 py-2 dark:border-white/5 dark:bg-[#25282d]"
                        >
                          <span className="truncate text-[13px] text-black/80 dark:text-white/80">
                            {file.name}
                          </span>
                          <button
                            type="button"
                            onClick={() => removeFile(index)}
                            className="rounded-full p-1 text-black/40 transition-colors hover:bg-black/10 hover:text-black dark:text-white/40 dark:hover:bg-white/10 dark:hover:text-white"
                            aria-label={`Remove ${file.name}`}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {!isRating && (
                <div className="mt-1 flex items-start gap-3">
                  <input
                    id="consent"
                    type="checkbox"
                    checked={consent}
                    onChange={(event) => setConsent(event.target.checked)}
                    className="mt-0.5 h-4 w-4 accent-[#4f55f1]"
                  />
                  <label
                    htmlFor="consent"
                    className="cursor-pointer select-none text-[13px] leading-snug text-black/60 dark:text-white/60"
                  >
                    {isFeature
                      ? t(
                          "feedback.consent_feature",
                          "I consent to the Argus team using this feature request and contacting me if follow-up would help.",
                        )
                      : t(
                          "feedback.consent",
                          "I consent to the Argus team processing this feedback and contacting me for follow-up details if necessary.",
                        )}
                  </label>
                </div>
              )}

              {error && (
                <p className="flex items-center gap-2 rounded-lg bg-[#d66d75]/10 px-4 py-2 text-[13px] font-medium text-[#d66d75]">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </p>
              )}

              <p className="text-[12px] leading-relaxed text-black/45 dark:text-white/45">
                {hasConversationContext
                  ? t(
                      "feedback.footer_note_conversation",
                      "Your current conversation context may be included to help us understand this feedback.",
                    )
                  : t(
                      "feedback.footer_note",
                      "App context like this page and timestamp may be included to help us understand this feedback.",
                    )}{" "}
                <button
                  type="button"
                  className="font-medium text-black underline underline-offset-2 hover:text-black/70 dark:text-white dark:hover:text-white/70"
                >
                  {t("common.learn_more", "Learn more")}
                </button>
              </p>

              <div className="mt-2 flex justify-end gap-3 border-t border-black/5 pt-4 dark:border-white/5">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-full border border-black/10 px-6 py-2.5 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:text-white dark:hover:bg-white/5"
                >
                  {t("common.cancel", "Cancel")}
                </button>
                <button
                  type="submit"
                  disabled={!canSubmit() || isSubmitting}
                  className="flex items-center gap-2 rounded-full bg-black px-6 py-2.5 text-[14px] font-medium text-white transition-opacity hover:opacity-90 disabled:pointer-events-none disabled:opacity-40 dark:bg-white dark:text-black"
                >
                  {isSubmitting ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  ) : (
                    t("feedback.submit", "Submit feedback")
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
