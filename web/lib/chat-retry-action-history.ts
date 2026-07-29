import type { Message } from "@/components/chat/types";
import { isRetryAction } from "./chat-retry-actions";

export function normalizeRetryActionHistory(messages: Message[]): Message[] {
  const latestIndex = messages.length - 1;
  return messages.flatMap((message, index) => {
    if (isSupersededRuntimeFailureMessage(message)) {
      return [];
    }
    if (!message.actions?.some(isRetryAction)) {
      return [message];
    }
    if (isLiveRetryMessage(message, index, latestIndex)) {
      return [message];
    }
    return [stripRetryActions(message)];
  });
}

function isLiveRetryMessage(
  message: Message,
  index: number,
  latestIndex: number,
): boolean {
  return index === latestIndex && message.role === "ai" && message.kind === "text";
}

function isSupersededRuntimeFailureMessage(message: Message): boolean {
  return (
    message.role === "ai" &&
    message.kind === "text" &&
    message.contentPresentation === "superseded_runtime_failure"
  );
}

/**
 * A superseded failure resolved in place: it stops rendering, and the
 * retry's duplicate request bubble goes with it. Telemetry keeps both in
 * durable metadata.
 */
export function retireSupersededFailures(messages: Message[]): Message[] {
  const retired: Message[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (isSupersededRuntimeFailureMessage(message)) {
      const request = retired[retired.length - 1];
      const duplicate = messages[index + 1];
      if (
        request?.role === "user" &&
        duplicate?.role === "user" &&
        normalizedContent(request) &&
        normalizedContent(request) === normalizedContent(duplicate)
      ) {
        retired.pop();
      }
      continue;
    }
    retired.push(message);
  }
  return retired;
}

function normalizedContent(message: Message): string {
  return (message.content ?? "").split(/\s+/).join(" ").trim().toLowerCase();
}

function stripRetryActions(message: Message): Message {
  const actions = message.actions?.filter((action) => !isRetryAction(action)) ?? [];
  return {
    ...message,
    actions: actions.length > 0 ? actions : undefined,
  };
}
