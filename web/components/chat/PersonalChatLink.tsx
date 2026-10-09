import Link from "next/link";
import { useTranslation } from "react-i18next";

/** Shown under a Business refusal only when the backend says Personal chat runs that function. */
export default function PersonalChatLink() {
  const { t } = useTranslation();
  return (
    <Link
      href="/chat"
      data-testid="personal-chat-link"
      className="mt-3 inline-flex min-h-11 items-center text-[13px] text-black/60 underline decoration-black/20 underline-offset-4 transition-colors hover:text-black dark:text-white/60 dark:decoration-white/20 dark:hover:text-white"
    >
      {t("chat.recovery_links.personal_chat")}
    </Link>
  );
}
