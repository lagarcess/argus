import type { StrategyConfirmationBenchmarkAdjustment } from "@/components/chat/types";

type BenchmarkTranslation = (
  key: string,
  options: { target: string; benchmark: string },
) => string;

export function confirmationBenchmarkAdjustmentText(
  adjustment: StrategyConfirmationBenchmarkAdjustment | null | undefined,
  translate: BenchmarkTranslation,
): string | null {
  if (!adjustment || adjustment.code !== "comparison_target_unsupported") {
    return null;
  }
  const target = adjustment.requested_target.trim();
  const benchmark = adjustment.effective_benchmark.trim();
  if (!target || !benchmark) {
    return null;
  }
  return translate("chat.confirmation.benchmark_adjustment", {
    target,
    benchmark,
  });
}
