"use client";

import { useTranslation } from "react-i18next";
import GuestLegalFooter, {
  type GuestLegalFooterVariant,
} from "@/components/guest/GuestLegalFooter";

type ChatLegalNoticeProps = {
  expiresAt: string | null | undefined;
  isGuest: boolean;
  showRegisteredDisclaimer?: boolean;
  variant: GuestLegalFooterVariant;
};

export default function ChatLegalNotice({
  expiresAt,
  isGuest,
  showRegisteredDisclaimer = false,
  variant,
}: ChatLegalNoticeProps) {
  const { t } = useTranslation();

  if (isGuest) {
    return <GuestLegalFooter expiresAt={expiresAt} variant={variant} />;
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
