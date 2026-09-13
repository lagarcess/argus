import type { Message } from "@/components/chat/types";

type SettledStrategyResult = Message & {
  kind: "strategy_result";
  result: NonNullable<Message["result"]>;
};

/** A result card that has settled. The card, the rail, and the feedback ask all read this one test. */
export function isSettledStrategyResult(
  message: Message,
): message is SettledStrategyResult {
  return (
    message.kind === "strategy_result" &&
    Boolean(message.result) &&
    !message.isLoadingResult
  );
}
