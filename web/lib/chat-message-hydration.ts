import type { ApiMessage } from "./argus-api";
import {
  failedActionRetryActionFromMetadata,
  retryLastTurnActionFromMetadata,
} from "./chat-retry-actions";
import {
  coverageRecoveryActionsFromMetadata,
  recoveryDisplayFromMetadata,
} from "./chat-recovery-display";
import { resultFactHeadingKeyFromMetadata } from "./result-followup-heading";
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
  const coverageActions = isAssistant
    ? coverageRecoveryActionsFromMetadata(metadata)
    : [];
  const actions = [...coverageActions, ...retryActions];

  return {
    id: message.id,
    role: message.role === "user" ? "user" : "ai",
    kind: "text",
    content: message.content,
    actions: isAssistant && actions.length > 0 ? actions : undefined,
    contentPresentation: isAssistant
      ? runtimeFailureContentPresentation(metadata, options.contentPresentation)
      : undefined,
    resultFactHeadingKey: isAssistant
      ? resultFactHeadingKeyFromMetadata(metadata)
      : undefined,
    recoveryDisplay: isAssistant
      ? recoveryDisplayFromMetadata(metadata)
      : undefined,
  };
}

function runtimeFailureContentPresentation(
  metadata: Record<string, unknown>,
  fallback: Message["contentPresentation"],
): Message["contentPresentation"] {
  if (metadata.agent_runtime_failure_superseded === true) {
    return "superseded_runtime_failure";
  }
  return fallback;
}
