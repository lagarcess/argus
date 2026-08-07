"use client";

import { useTranslation } from "react-i18next";
import ChatInput from "./ChatInput";
import ChatLegalNotice from "./ChatLegalNotice";
import EmptyChatGreeting from "./EmptyChatGreeting";
import EmptyChatHeading from "./EmptyChatHeading";
import StarterActions, {
  type StarterSelectionMetadata,
} from "./StarterActions";
import type { ChatMention } from "./types";
import { researchRailEnabled } from "@/lib/private-alpha-flags";

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

  const showSignedInGreeting = researchRailEnabled && !isGuest;

  return (
    <div className="flex h-full flex-col items-center justify-start overflow-y-auto px-4 pb-8 pt-[24vh] sm:pt-[28vh]">
      {showSignedInGreeting ? (
        <EmptyChatGreeting />
      ) : (
        <EmptyChatHeading isGuest={isGuest} />
      )}

      <div
        aria-busy={guestSubmissionPending}
        className={
          showSignedInGreeting
            ? "order-3 w-full max-w-2xl"
            : "w-full max-w-2xl"
        }
      >
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
          showRegisteredDisclaimer={showSignedInGreeting}
          showGuestSafetyLine={researchRailEnabled}
          variant="before_message"
        />
      </div>

      {/* One owner for the chips. Spec section 10 orders the signed-in rail
          surface as greeting, suggestions, composer at the bottom; flex order
          does the reordering so the flag-off DOM stays identical. */}
      {(!showSignedInGreeting || showSuggestions) && (
        <StarterActions
          disabled={disabled}
          onSelect={onSend}
          className={showSignedInGreeting ? " order-2 mb-2" : ""}
        />
      )}

      {showSignedInGreeting && (
        <div className="order-4 mt-4">
          <button
            onClick={onToggleSuggestions}
            className="min-h-11 rounded-full px-3 text-[14px] font-medium text-black/60 transition-colors hover:text-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:text-white/60 dark:hover:text-white dark:focus-visible:ring-white/25"
          >
            {showSuggestions
              ? t("chat.hide_suggestions")
              : t("chat.show_suggestions")}
          </button>
        </div>
      )}
    </div>
  );
}
