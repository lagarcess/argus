"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { X, Send, AlertCircle, Sparkles, MessageSquare, ThumbsUp, ThumbsDown, Paperclip, ChevronDown, Check, Bug, Lightbulb, MessageCircle } from "lucide-react";
import { postFeedback } from "@/lib/argus-api";

type FeedbackType = "bug" | "feature" | "general" | "rating";

interface FeedbackDialogProps {
  isOpen: boolean;
  onClose: () => void;
  type: FeedbackType;
  rating?: "positive" | "negative";
  context?: Record<string, unknown>;
}

export default function FeedbackDialog({ isOpen, onClose, type: initialType, rating, context }: FeedbackDialogProps) {
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
    if (isOpen) {
      setType(initialType);
      setMessage("");
      setBugTitle("");
      setSteps("");
      setExpected("");
      setActual("");
      setConsent(false);
      setFiles([]);
      setSelectedTags([]);
      setIsSuccess(false);
      setError(null);
      setDropdownOpen(false);
    }
  }, [isOpen, initialType]);

  if (!isOpen) return null;

  const isRating = type === "rating";
  const isBug = type === "bug";

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      if (files.length + newFiles.length > 5) {
        setError("Maximum 5 files allowed.");
        return;
      }
      setFiles(prev => [...prev, ...newFiles].slice(0, 5));
      setError(null);
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const canSubmit = () => {
    if (isRating) return selectedTags.length > 0 || message.trim().length > 0;
    if (!consent) return false;
    if (isBug) return bugTitle.trim().length > 0 && steps.trim().length > 0;
    return message.trim().length > 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit()) return;

    setIsSubmitting(true);
    setError(null);

    let finalMessage = message.trim();
    if (isBug) {
      finalMessage = `Title: ${bugTitle}\n\nSteps to reproduce:\n${steps}\n\nExpected outcome:\n${expected}\n\nActual outcome:\n${actual}`;
    }

    try {
      await postFeedback({
        type: isRating ? "general" : type,
        message: finalMessage || (isRating ? `${rating} rating with tags` : ""),
        context: {
          ...context,
          rating,
          tags: selectedTags,
          url: typeof window !== "undefined" ? window.location.href : undefined,
          timestamp: new Date().toISOString(),
          hasAttachments: files.length > 0, // Stub for now
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

  const toggleTag = (tagKey: string) => {
    setSelectedTags(prev => prev.includes(tagKey) ? prev.filter(t => t !== tagKey) : [...prev, tagKey]);
  };

  const typeOptions: { value: FeedbackType; label: string; icon: React.ReactNode }[] = [
    { value: "general", label: "General Feedback", icon: <MessageCircle className="w-4 h-4" /> },
    { value: "bug", label: "Report a Bug", icon: <Bug className="w-4 h-4" /> },
    { value: "feature", label: "Request a Feature", icon: <Lightbulb className="w-4 h-4" /> },
  ];

  const currentType = typeOptions.find(t => t.value === type) || typeOptions[0];

  const ratingTags = rating === "positive"
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

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/20 dark:bg-black/60 backdrop-blur-sm animate-in fade-in duration-300" onClick={onClose} />
      
      <div className="relative w-full max-w-[600px] max-h-[90vh] flex flex-col bg-[#f5f5f5] dark:bg-[#1c1f24] border border-black/5 dark:border-white/10 rounded-[28px] overflow-hidden animate-in zoom-in-95 fade-in duration-300 shadow-2xl">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-6 sm:px-8 py-6 border-b border-black/5 dark:border-white/5">
          <div className="flex flex-col">
            <h2 className="text-[22px] font-display font-semibold tracking-tight text-black dark:text-white">
              {isRating ? (rating === "positive" ? "Provide positive feedback" : "Provide negative feedback") : "Provide Feedback"}
            </h2>
            {!isRating && (
              <p className="text-[13px] text-black/50 dark:text-white/50 mt-1">
                Help us improve Argus.
              </p>
            )}
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
            <X className="w-5 h-5 text-black/40 dark:text-white/40" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-8 argus-thin-scrollbar">
          {isSuccess ? (
            <div className="py-12 text-center animate-in zoom-in-95 duration-300">
              <div className="w-16 h-16 bg-[#5ba897]/10 rounded-full flex items-center justify-center mx-auto mb-5">
                <Send className="w-7 h-7 text-[#5ba897]" />
              </div>
              <p className="text-[18px] font-display font-medium text-black dark:text-white">
                Feedback submitted. Thank you!
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-6">
              
              {/* Dropdown Type Selector (Hidden for rating) */}
              {!isRating && (
                <div className="relative">
                  <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2 uppercase tracking-wide">
                    Feedback Type
                  </label>
                  <button
                    type="button"
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="flex w-full items-center justify-between bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 text-[14px] text-black dark:text-white hover:border-black/20 dark:hover:border-white/20 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-black/40 dark:text-white/40">{currentType.icon}</span>
                      <span className="font-medium">{currentType.label}</span>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-black/40 dark:text-white/40 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                  </button>
                  
                  {dropdownOpen && (
                    <div className="absolute top-[calc(100%+8px)] left-0 w-full bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl shadow-lg z-10 overflow-hidden py-1 animate-in fade-in slide-in-from-top-2">
                      {typeOptions.map(opt => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => { setType(opt.value); setDropdownOpen(false); }}
                          className="flex w-full items-center gap-3 px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 text-[14px] text-left text-black dark:text-white"
                        >
                          <span className="text-black/40 dark:text-white/40">{opt.icon}</span>
                          <span className="font-medium flex-1">{opt.label}</span>
                          {type === opt.value && <Check className="w-4 h-4 text-[#4f55f1]" />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Bug Form */}
              {isBug && !isRating ? (
                <>
                  <div>
                    <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Title *</label>
                    <input
                      value={bugTitle}
                      onChange={(e) => setBugTitle(e.target.value.slice(0, 100))}
                      placeholder="Brief description of the issue"
                      className="w-full bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 text-[14px] text-black dark:text-white outline-none focus:border-[#4f55f1] transition-colors placeholder:text-black/30 dark:placeholder:text-white/30"
                    />
                    <div className="text-right text-[11px] text-black/30 mt-1">{bugTitle.length}/100</div>
                  </div>
                  <div>
                    <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Steps to reproduce *</label>
                    <textarea
                      value={steps}
                      onChange={(e) => setSteps(e.target.value.slice(0, 1000))}
                      placeholder={"1. Go to [Page/View]\n2. Click on [Button/Action]\n3. See [Error/Behavior]"}
                      className="w-full min-h-[100px] bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 text-[14px] text-black dark:text-white outline-none focus:border-[#4f55f1] transition-colors resize-y placeholder:text-black/30 dark:placeholder:text-white/30"
                    />
                    <div className="text-right text-[11px] text-black/30 mt-1">{steps.length}/1000</div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Expected outcome</label>
                      <textarea
                        value={expected}
                        onChange={(e) => setExpected(e.target.value.slice(0, 500))}
                        className="w-full min-h-[80px] bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 text-[14px] text-black dark:text-white outline-none focus:border-[#4f55f1] transition-colors resize-none placeholder:text-black/30 dark:placeholder:text-white/30"
                      />
                    </div>
                    <div>
                      <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Actual outcome</label>
                      <textarea
                        value={actual}
                        onChange={(e) => setActual(e.target.value.slice(0, 500))}
                        className="w-full min-h-[80px] bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 text-[14px] text-black dark:text-white outline-none focus:border-[#4f55f1] transition-colors resize-none placeholder:text-black/30 dark:placeholder:text-white/30"
                      />
                    </div>
                  </div>
                </>
              ) : (
                /* General/Feature/Rating Form */
                <div className={isRating ? "space-y-6" : ""}>
                  {isRating && (
                    <div>
                      <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-3">What {rating === "positive" ? "went well" : "went wrong"}?</label>
                      <div className="flex flex-wrap gap-2">
                        {ratingTags.map((tag) => (
                          <button
                            key={tag.key}
                            type="button"
                            onClick={() => toggleTag(tag.key)}
                            className={`px-4 py-2 rounded-full text-[13px] font-medium border transition-all ${ selectedTags.includes(tag.key) ? "bg-black dark:bg-white text-white dark:text-black border-transparent" : "bg-white dark:bg-[#25282d] border-black/10 dark:border-white/10 text-black/70 dark:text-white/70 hover:border-black/20 dark:hover:border-white/30" }`}
                          >
                            {tag.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    {!isRating && <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Details *</label>}
                    {isRating && <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Additional details</label>}
                    <textarea
                      autoFocus={!isRating}
                      value={message}
                      onChange={(e) => setMessage(e.target.value.slice(0, 1000))}
                      placeholder={isRating ? "Tell us more about your experience..." : "What's on your mind?"}
                      className="w-full min-h-[140px] bg-white dark:bg-[#25282d] border border-black/10 dark:border-white/10 rounded-xl px-4 py-3 text-[14px] text-black dark:text-white outline-none focus:border-[#4f55f1] transition-colors resize-y placeholder:text-black/30 dark:placeholder:text-white/30"
                    />
                    <div className="text-right text-[11px] text-black/30 dark:text-white/30 mt-1">{message.length}/1000</div>
                  </div>
                </div>
              )}

              {/* Attachments */}
              {!isRating && (
                <div>
                  <label className="block text-[13px] font-medium text-black/60 dark:text-white/60 mb-2">Attachments</label>
                  <div 
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full border border-dashed border-black/20 dark:border-white/20 rounded-xl p-6 flex flex-col items-center justify-center cursor-pointer hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  >
                    <Paperclip className="w-5 h-5 text-black/40 dark:text-white/40 mb-2" />
                    <p className="text-[13px] text-black/60 dark:text-white/60">Click to attach files (max 5)</p>
                  </div>
                  <input type="file" multiple ref={fileInputRef} onChange={handleFileChange} className="hidden" />
                  
                  {files.length > 0 && (
                    <div className="mt-3 flex flex-col gap-2">
                      {files.map((file, i) => (
                        <div key={i} className="flex items-center justify-between bg-white dark:bg-[#25282d] border border-black/5 dark:border-white/5 rounded-lg px-3 py-2">
                          <span className="text-[13px] text-black/80 dark:text-white/80 truncate">{file.name}</span>
                          <button type="button" onClick={() => removeFile(i)} className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-full text-black/40 dark:text-white/40">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Consent */}
              {!isRating && (
                <div className="flex items-start gap-3 mt-2">
                  <input 
                    type="checkbox" 
                    id="consent" 
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-0.5 accent-[#4f55f1] w-4 h-4 rounded-sm"
                  />
                  <label htmlFor="consent" className="text-[13px] text-black/60 dark:text-white/60 leading-snug cursor-pointer select-none">
                    I consent to the Argus team processing this feedback and contacting me for follow-up details if necessary.
                  </label>
                </div>
              )}

              {error && (
                <p className="text-[13px] text-[#d66d75] font-medium bg-[#d66d75]/10 px-4 py-2 rounded-lg">
                  {error}
                </p>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t border-black/5 dark:border-white/5 mt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-6 py-2.5 text-[14px] font-medium rounded-full border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-black dark:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!canSubmit() || isSubmitting}
                  className="px-6 py-2.5 text-[14px] font-medium rounded-full bg-black dark:bg-white text-white dark:text-black hover:opacity-90 transition-opacity disabled:opacity-40 disabled:pointer-events-none flex items-center gap-2"
                >
                  {isSubmitting ? (
                    <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  ) : "Submit Feedback"}
                </button>
              </div>

            </form>
          )}
        </div>
      </div>
    </div>
  );
}
