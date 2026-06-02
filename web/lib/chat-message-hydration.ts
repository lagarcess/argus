import type { ApiMessage } from "./argus-api";
import {
  failedActionRetryActionFromMetadata,
  retryLastTurnActionFromMetadata,
} from "./chat-retry-actions";
import type { ChatActionOption, Message } from "@/components/chat/types";

type TextMessageHydrationOptions = {
  contentPresentation?: Message["contentPresentation"];
};

function retryActionsFromMetadata(
  metadata: Record<string, unknown>,
  assistantMessageId: string,
): ChatActionOption[] {
  return [
    failedActionRetryActionFromMetadata(metadata),
    retryLastTurnActionFromMetadata(metadata, { assistantMessageId }),
  ].filter((action): action is ChatActionOption => Boolean(action));
}

export function hydrateTextMessageFromApi(
  message: ApiMessage,
  options: TextMessageHydrationOptions = {},
): Message {
  const metadata = message.metadata ?? {};
  const isAssistant = message.role !== "user";
  const retryActions = isAssistant
    ? retryActionsFromMetadata(metadata, message.id)
    : [];

  return {
    id: message.id,
    role: message.role === "user" ? "user" : "ai",
    kind: "text",
    content: message.content,
    actions: isAssistant && retryActions.length > 0 ? retryActions : undefined,
    contentPresentation: isAssistant ? options.contentPresentation : undefined,
  };
}
