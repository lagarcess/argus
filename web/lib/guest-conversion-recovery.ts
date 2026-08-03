import type { ChatActionOption } from "@/components/chat/types";

export function isGuestSimulationConversionRejection(
  failureCode: unknown,
  action: ChatActionOption | undefined,
): action is ChatActionOption & { type: "run_backtest" } {
  return (
    failureCode === "account_conversion_required" &&
    action?.type === "run_backtest"
  );
}
