"use client";

import { Bitcoin, LineChart, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { captureGuestFunnelEvent } from "@/lib/guest-analytics";
import { normalizeEnabledLanguage } from "@/lib/language-features";

type StarterActionsProps = {
  onSelect: (value: string) => void;
  disabled?: boolean;
  guestAnalyticsEnabled?: boolean;
};

export default function StarterActions({
  onSelect,
  disabled = false,
  guestAnalyticsEnabled = false,
}: StarterActionsProps) {
  const { t, i18n } = useTranslation();
  const actions = [
    {
      key: "tsla",
      strategy_category: "buy_and_hold" as const,
      icon: TrendingUp,
      label: t("chat.starter_actions.tsla.label", "Test Apple vs SPY"),
      value: t(
        "chat.starter_actions.tsla.value",
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark.",
      ),
    },
    {
      key: "btc",
      strategy_category: "buy_and_hold" as const,
      icon: Bitcoin,
      label: t("chat.starter_actions.btc.label", "Test Bitcoin (BTC) hold"),
      value: t(
        "chat.starter_actions.btc.value",
        "What if I bought Bitcoin this year so far?",
      ),
    },
    {
      key: "dca",
      strategy_category: "dca_accumulation" as const,
      icon: LineChart,
      label: t(
        "chat.starter_actions.dca.label",
        "Test weekly Nvidia buys",
      ),
      value: t(
        "chat.starter_actions.dca.value",
        "What if I bought $250 of Nvidia every week over the last 12 months?",
      ),
    },
  ];

  return (
    <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
      {actions.map(({ key, strategy_category, icon: Icon, label, value }) => (
        <button
          key={key}
          type="button"
          disabled={disabled}
          onClick={() => {
            if (guestAnalyticsEnabled) {
              captureGuestFunnelEvent({
                event: "starter_action_selected",
                language: normalizeEnabledLanguage(i18n.resolvedLanguage),
                surface: "starter_actions",
                strategy_category,
                terminal_outcome: "selected",
              });
            }
            onSelect(value);
          }}
          className="flex min-h-11 items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
        >
          <Icon className="h-4 w-4 text-black/60 dark:text-white/60" />
          {label}
        </button>
      ))}
    </div>
  );
}
