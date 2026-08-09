"use client";

import { useTranslation } from "react-i18next";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
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
  /** A setting the user stated, never something Argus inferred. */
  preferredName?: string | null;
  placeholder: string;
  onSend: (
    text: string,
    selection?: ChatMention[] | StarterSelectionMetadata,
  ) => void | boolean | Promise<void | boolean>;
  onRetryGuestSubmission: () => void;
  onToast: (message: string) => void;
};

export default function EmptyChatSurface({
  isGuest,
  expiresAt,
  guestSubmissionPending,
  guestSubmissionError,
  isStreamingResponse,
  isHydratingConversation,
  preferredName,
  placeholder,
  onSend,
  onRetryGuestSubmission,
  onToast,
}: EmptyChatSurfaceProps) {
  const { t } = useTranslation();
  const { isBelowTablet } = useResponsiveLayout();
  const disabled =
    isStreamingResponse || isHydratingConversation || guestSubmissionPending;

  const showSignedInGreeting = researchRailEnabled && !isGuest;

  // The tall top inset belongs to tablet and up. Expressing it as a min-width
  // variant rather than overriding a base value keeps `sm:` from winning the
  // cascade between 400 and 719px, where most phones actually sit.
  return (
    <div className="flex h-full flex-col items-center justify-start overflow-y-auto px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-6 tablet:pb-8 tablet:pt-[28vh]">
      {/* The heading absorbs the free space below the mobile threshold, which
          settles the pills and the composer onto the bottom edge where a thumb
          rests. Above it, the surface keeps its centered composition. */}
      <div className="order-1 flex w-full flex-col items-center max-tablet:flex-1 max-tablet:justify-center">
        {showSignedInGreeting ? (
          // Guests have no profile, so they never reach this and always get the
          // nameless pool.
          <EmptyChatGreeting preferredName={preferredName} />
        ) : (
          <EmptyChatHeading isGuest={isGuest} />
        )}
      </div>

      <div
        aria-busy={guestSubmissionPending}
        className={
          showSignedInGreeting
            ? "order-3 w-full max-w-2xl"
            : "order-3 w-full max-w-2xl tablet:order-2"
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

      {/* One owner for the chips, and they are always on. Flag off, this is
          integration's shipped placement: thumb-reachable above the composer on
          narrow screens, under it from tablet up. Flag on, spec section 10
          keeps them above the composer at every width. They stop on their own
          once a conversation has a message, because this surface stops
          rendering. */}
      <div
        className={
          showSignedInGreeting
            ? "order-2 w-full max-w-2xl max-tablet:mb-3 tablet:mb-2"
            : "order-2 w-full max-w-2xl max-tablet:mb-3 tablet:order-3"
        }
      >
        <StarterActions
          disabled={disabled}
          onSelect={onSend}
          layout={isBelowTablet ? "scroll" : "wrap"}
        />
      </div>
    </div>
  );
}
