import type { ApiMessage } from "./argus-api";
import {
  failedActionRetryActionFromMetadata,
  retryLastTurnActionFromMetadata,
} from "./chat-retry-actions";
import {
  coverageRecoveryActionsFromMetadata,
  recoveryDisplayFromMetadata,
  recoveryDisplayFromRecoveryState,
  unsupportedTimeframeActionsFromMetadata,
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

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

// #240: the persisted user message carries the abandoned-turn overlay; one
// presentation-only recovery attachment derives from it. It has no message
// identity of its own, so it stays with its owner across cursor pages.
function abandonedRecoveryFromMetadata(
  metadata: Record<string, unknown>,
): Message["abandonedRecovery"] {
  const turn = recordOrNull(metadata.agent_runtime_turn);
  if (turn?.status !== "abandoned" || turn?.terminal !== true) {
    return undefined;
  }
  const display = recoveryDisplayFromRecoveryState(metadata.recovery);
  const action = retryLastTurnActionFromMetadata(metadata);
  if (!display || !action) {
    return undefined;
  }
  return { display, action };
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
    ? coverageRecoveryActionsFromMetadata(metadata, message.id)
    : [];
  const unsupportedTimeframeActions = isAssistant
    ? unsupportedTimeframeActionsFromMetadata(metadata, message.id)
    : [];
  const actions = [
    ...coverageActions,
    ...unsupportedTimeframeActions,
    ...retryActions,
  ];

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
    abandonedRecovery: isAssistant
      ? undefined
      : abandonedRecoveryFromMetadata(metadata),
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
