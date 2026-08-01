"use client";

import { useTranslation } from "react-i18next";
import ChatInput from "./ChatInput";
import ChatLegalNotice from "./ChatLegalNotice";
import EmptyChatHeading from "./EmptyChatHeading";
import StarterActions, {
  type StarterSelectionMetadata,
} from "./StarterActions";
import type { ChatMention } from "./types";
import { chatExploratorySuggestionsEnabled } from "@/lib/private-alpha-flags";

type EmptyChatSurfaceProps = {
  isGuest: boolean;
  expiresAt?: string | null;
  guestSubmissionPending: boolean;
  guestSubmissionError: boolean;
  isStreamingResponse: boolean;
  isHydratingConversation: boolean;
  showSuggestions: boolean;
  placeholder: string;
  onSend: (
    text: string,
    selection?: ChatMention[] | StarterSelectionMetadata,
  ) => void | boolean | Promise<void | boolean>;
  onRetryGuestSubmission: () => void;
  onToggleSuggestions: () => void;
  onToast: (message: string) => void;
};

export default function EmptyChatSurface({
  isGuest,
  expiresAt,
  guestSubmissionPending,
  guestSubmissionError,
  isStreamingResponse,
  isHydratingConversation,
  showSuggestions,
  placeholder,
  onSend,
  onRetryGuestSubmission,
  onToggleSuggestions,
  onToast,
}: EmptyChatSurfaceProps) {
  const { t } = useTranslation();
  const disabled =
    isStreamingResponse || isHydratingConversation || guestSubmissionPending;

  return (
    <div className="flex h-full flex-col items-center justify-start overflow-y-auto px-4 pb-8 pt-[24vh] sm:pt-[28vh]">
      <EmptyChatHeading isGuest={isGuest} />

      <div aria-busy={guestSubmissionPending} className="w-full max-w-2xl">
        <ChatInput
          key="new-conversation"
          onSend={onSend}
          disabled={disabled}
          placeholder={placeholder}
          onToast={onToast}
        />
        {guestSubmissionPending && (
          <div
            aria-label={t("guest.entry.sending", "Sending...")}
            className="mt-3 flex justify-center"
            role="status"
          >
            <span
              aria-hidden="true"
              className="h-4 w-4 animate-spin rounded-full border-2 border-black/25 border-t-black/70 dark:border-white/25 dark:border-t-white/70"
            />
            <span className="sr-only">
              {t("guest.entry.sending", "Sending...")}
            </span>
          </div>
        )}
        {guestSubmissionError && !guestSubmissionPending && (
          <div
            className="mt-3 flex flex-wrap items-center justify-center gap-2 text-center text-sm text-red-600 dark:text-red-300"
            role="alert"
          >
            <span>{t("guest.entry.error")}</span>
            <button
              type="button"
              className="min-h-11 rounded-full border border-current px-4 py-2 font-medium"
              onClick={onRetryGuestSubmission}
            >
              {t("common.try_again", "Try again")}
            </button>
          </div>
        )}
        <ChatLegalNotice
          expiresAt={expiresAt}
          isGuest={isGuest}
          variant="before_message"
        />
      </div>

      <StarterActions disabled={disabled} onSelect={onSend} />

      {chatExploratorySuggestionsEnabled && (
        <div className="mt-4">
          <button
            onClick={onToggleSuggestions}
            className="text-[14px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white"
          >
            {showSuggestions
              ? t("chat.hide_suggestions")
              : t("chat.show_suggestions")}
          </button>
        </div>
      )}

      {chatExploratorySuggestionsEnabled && showSuggestions && (
        <div className="mt-8 flex flex-col items-center gap-4 text-center">
          {(["q1", "q2", "q3"] as const).map((queryKey) => {
            const fallback = {
              q1: "What if I bought Apple after big drops?",
              q2: "What if I bought Bitcoin when it starts rising?",
              q3: "What if I bought Tesla every month?",
            }[queryKey];
            const prompt = t(`chat.example_queries.${queryKey}`, fallback);
            return (
              <button
                key={queryKey}
                onClick={() => onSend(prompt)}
                className="text-[14px] text-black/50 transition-colors hover:text-black hover:underline dark:text-white/50 dark:hover:text-white"
              >
                {prompt}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
