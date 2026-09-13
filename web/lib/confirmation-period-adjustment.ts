import type { StrategyConfirmationPeriodAdjustment } from "@/components/chat/types";

type PeriodTranslation = (
  key: string,
  options: { period: string; symbol?: string; date?: string },
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
  const period = `${formatter.format(startDate)} – ${formatter.format(endDate)}`;
  const limitedBy = adjustment.limited_by;
  const symbol = limitedBy?.symbol.trim() ?? "";
  const firstAvailable = limitedBy
    ? new Date(`${limitedBy.first_available}T00:00:00Z`)
    : null;
  // Older cards without a limiting asset keep the shared data window reason.
  if (symbol && firstAvailable && !Number.isNaN(firstAvailable.getTime())) {
    return translate("chat.confirmation.period_adjustment_limited_by", {
      period,
      symbol,
      date: formatter.format(firstAvailable),
    });
  }
  return translate("chat.confirmation.period_adjustment", { period });
}
