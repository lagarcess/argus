import type { Message } from "@/components/chat/types";
import { isRetryAction } from "./chat-retry-actions";

export function normalizeRetryActionHistory(messages: Message[]): Message[] {
  const latestIndex = messages.length - 1;
  return messages.map((message, index) => {
    if (!message.actions?.some(isRetryAction)) {
      return message;
    }
    if (isLiveRetryMessage(message, index, latestIndex)) {
      return message;
    }
    return stripRetryActions(message);
  });
}

function isLiveRetryMessage(
  message: Message,
  index: number,
  latestIndex: number,
): boolean {
  return index === latestIndex && message.role === "ai" && message.kind === "text";
}

function stripRetryActions(message: Message): Message {
  const actions = message.actions?.filter((action) => !isRetryAction(action)) ?? [];
  return {
    ...message,
    actions: actions.length > 0 ? actions : undefined,
  };
}
