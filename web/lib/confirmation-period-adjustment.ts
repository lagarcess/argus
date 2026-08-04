import type { StrategyConfirmationPeriodAdjustment } from "@/components/chat/types";

type PeriodTranslation = (
  key: string,
  options: { period: string },
) => string;

export function confirmationPeriodAdjustmentText(
  adjustment: StrategyConfirmationPeriodAdjustment | null | undefined,
  translate: PeriodTranslation,
  locale: string,
): string | null {
  if (!adjustment || adjustment.code !== "effective_window_adjusted") {
    return null;
  }
  const formatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  const startDate = new Date(
    `${adjustment.effective_date_range.start}T00:00:00Z`,
  );
  const endDate = new Date(`${adjustment.effective_date_range.end}T00:00:00Z`);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return null;
  }
  const start = formatter.format(startDate);
  const end = formatter.format(endDate);
  return translate("chat.confirmation.period_adjustment", {
    period: `${start} – ${end}`,
  });
}
