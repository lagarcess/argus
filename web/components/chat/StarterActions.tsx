"use client";

import { Bitcoin, LineChart, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { researchRailEnabled } from "@/lib/private-alpha-flags";

export type StarterSelectionMetadata = {
  strategy_category: "buy_and_hold" | "dca_accumulation";
};

type StarterActionsProps = {
  onSelect: (value: string, metadata?: StarterSelectionMetadata) => void;
  disabled?: boolean;
  className?: string;
};

const pillClassName =
  "flex min-h-11 items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5";

export default function StarterActions({
  onSelect,
  disabled = false,
  className = "",
}: StarterActionsProps) {
  const { t } = useTranslation();

  if (researchRailEnabled) {
    // The static chips are the universal fallback, not guest-only code: every
    // account without memory-driven suggestions gets these. Three shapes span
    // the range (learn, compare, test); each is something a user would say,
    // never a capability label.
    const queries = (["q1", "q2", "q3"] as const).map((queryKey) => ({
      key: queryKey,
      value: t(`chat.example_queries.${queryKey}`, {
        q1: "How does Netflix make money?",
        q2: "Compare Costco against Walmart and Target",
        q3: "What if I had bought Coca-Cola every month for five years?",
      }[queryKey]),
    }));
    return (
      <div
        className={`mt-6 flex flex-wrap items-center justify-center gap-3${className}`}
      >
        {queries.map(({ key, value }) => (
          <button
            key={key}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(value)}
            className={pillClassName}
          >
            {value}
          </button>
        ))}
      </div>
    );
  }

  const actions = [
    {
      key: "tsla",
      strategy_category: "buy_and_hold" as const,
      icon: TrendingUp,
      label: t("chat.starter_actions.tsla.label", "Test Apple vs SPY"),
      value: t(
        "chat.starter_actions.tsla.value",
        "Compare Apple with SPY over the last 12 months.",
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
    <div
      className={`mt-6 flex flex-wrap items-center justify-center gap-3${className}`}
    >
      {actions.map(({ key, strategy_category, icon: Icon, label, value }) => (
        <button
          key={key}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(value, { strategy_category })}
          className={pillClassName}
        >
          <Icon className="h-4 w-4 text-black/60 dark:text-white/60" />
          {label}
        </button>
      ))}
    </div>
  );
}
