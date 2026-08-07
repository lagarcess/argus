"use client";

import { useTranslation } from "react-i18next";
import GuestLegalFooter, {
  type GuestLegalFooterVariant,
} from "@/components/guest/GuestLegalFooter";

type ChatLegalNoticeProps = {
  expiresAt: string | null | undefined;
  isGuest: boolean;
  showRegisteredDisclaimer?: boolean;
  /* The not-advice framing must stay visible on the guest entry too; research
   * answers read more authoritative than a backtest chart, so the empty state
   * carries the safety sentence alongside the agreement line. */
  showGuestSafetyLine?: boolean;
  variant: GuestLegalFooterVariant;
};

export default function ChatLegalNotice({
  expiresAt,
  isGuest,
  showRegisteredDisclaimer = false,
  showGuestSafetyLine = false,
  variant,
}: ChatLegalNoticeProps) {
  const { t } = useTranslation();

  if (isGuest) {
    return (
      <>
        {showGuestSafetyLine && (
          <p
            data-testid="guest-safety-note"
            className="mt-3 text-center text-[13px] font-normal leading-[1.45] text-black/40 dark:text-white/40"
          >
            {t(
              "guest.shell.after_message.safety",
              "Argus can make mistakes. For education only. Not financial advice.",
            )}
          </p>
        )}
        <GuestLegalFooter expiresAt={expiresAt} variant={variant} />
      </>
    );
  }
  if (!showRegisteredDisclaimer) return null;

  return (
    <p
      data-testid="chat-disclaimer"
      className="mt-3 text-center text-[13px] font-normal leading-[1.45] text-black/40 dark:text-white/40"
    >
      {t(
        "chat.disclaimer",
        "Argus can make mistakes. For education only. Not financial advice.",
      )}
    </p>
  );
}
