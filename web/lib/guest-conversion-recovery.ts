import type { ChatActionOption } from "@/components/chat/types";

export function isGuestSimulationConversionRejection(
  failureCode: unknown,
  action: ChatActionOption | undefined,
): boolean {
  return (
    failureCode === "account_conversion_required" &&
    action?.type === "run_backtest"
  );
}
