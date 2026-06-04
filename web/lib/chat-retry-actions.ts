import type { ChatActionOption } from "@/components/chat/types";

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function failedActionPayloadFromMetadata(
  metadata: Record<string, unknown>,
): {
  artifactId: string | null;
  artifactStatus: string | null;
  launchPayload: Record<string, unknown> | null;
  retryable: unknown;
} | null {
  const reference = recordOrNull(metadata.latest_failed_action_reference);
  const referenceMetadata = recordOrNull(reference?.metadata);
  const failedAction = recordOrNull(metadata.failed_action) ?? referenceMetadata;
  if (!reference && !failedAction) {
    return null;
  }

  const retryable =
    failedAction?.retryable ?? referenceMetadata?.retryable ?? metadata.retryable;

  const launchPayload =
    recordOrNull(failedAction?.launch_payload) ??
    recordOrNull(referenceMetadata?.launch_payload);
  if (!launchPayload) {
    return null;
  }

  return {
    artifactId:
      stringOrNull(reference?.artifact_id) ??
      stringOrNull(failedAction?.artifact_id),
    artifactStatus:
      stringOrNull(reference?.artifact_status) ??
      stringOrNull(failedAction?.artifact_status),
    launchPayload,
    retryable,
  };
}

function retryableFailedActionPayload(metadata: Record<string, unknown>) {
  const failedAction = failedActionPayloadFromMetadata(metadata);
  if (!failedAction || failedAction.retryable !== true) {
    return null;
  }
  return failedAction;
}

export function hasFailedActionMetadata(
  metadata: Record<string, unknown>,
): boolean {
  return failedActionPayloadFromMetadata(metadata) !== null;
}

export function failedActionRetryActionFromMetadata(
  metadata: Record<string, unknown>,
): ChatActionOption | null {
  const failedAction = retryableFailedActionPayload(metadata);
  if (!failedAction) {
    return null;
  }
  const artifactId = failedAction.artifactId;
  if (!artifactId) {
    return null;
  }
  return {
    id: `retry-failed-action-${artifactId}`,
    label: "Retry",
    labelKey: "common.retry",
    value: "Retry",
    type: "retry_failed_action",
    artifactId,
    artifactType: "failed_action",
    artifactStatus: failedAction.artifactStatus ?? "failed",
    payload: {
      failed_action_id: artifactId,
    },
  };
}

type RetryLastTurnOptions = {
  assistantMessageId?: string;
};

export function retryLastTurnActionFromMessage(
  message: string,
  options?: RetryLastTurnOptions,
): ChatActionOption | null {
  const trimmed = message.trim();
  if (!trimmed) {
    return null;
  }
  const failedAssistantId = options?.assistantMessageId?.trim();
  return {
    id: "retry-last-turn",
    label: "Retry",
    labelKey: "common.retry",
    value: "Retry",
    type: "retry_last_turn",
    payload: {
      message: trimmed,
      ...(failedAssistantId ? { failed_assistant_id: failedAssistantId } : {}),
    },
  };
}

export function retryLastTurnActionFromMetadata(
  metadata: Record<string, unknown>,
  options?: RetryLastTurnOptions,
): ChatActionOption | null {
  const retryLastTurn = recordOrNull(metadata.retry_last_turn);
  const message = stringOrNull(retryLastTurn?.message);
  if (!message) {
    return null;
  }
  return retryLastTurnActionFromMessage(message, options);
}

export function retryLastTurnMessageFromAction(
  action: ChatActionOption | null | undefined,
): string | null {
  if (action?.type !== "retry_last_turn") {
    return null;
  }
  const message = stringOrNull(action.payload?.message);
  return message?.trim() || null;
}

export function retryLastTurnFailedAssistantIdFromAction(
  action: ChatActionOption | null | undefined,
): string | null {
  if (action?.type !== "retry_last_turn") {
    return null;
  }
  return stringOrNull(action.payload?.failed_assistant_id)?.trim() || null;
}

export function conversationLoadRetryActionFromConversationId(
  conversationId: string | null | undefined,
): ChatActionOption | null {
  const trimmed = conversationId?.trim();
  if (!trimmed) {
    return null;
  }
  return {
    id: "retry-load-conversation",
    label: "Retry",
    labelKey: "common.retry",
    value: "Retry",
    type: "retry_load_conversation",
    payload: {
      conversation_id: trimmed,
    },
  };
}

export function retryLoadConversationIdFromAction(
  action: ChatActionOption | null | undefined,
): string | null {
  if (action?.type !== "retry_load_conversation") {
    return null;
  }
  return stringOrNull(action.payload?.conversation_id)?.trim() || null;
}

export function isRetryAction(action: ChatActionOption | null | undefined): boolean {
  if (!action) {
    return false;
  }
  return (
    action.type === "retry_failed_action" ||
    action.type === "retry_last_turn" ||
    action.type === "retry_load_conversation" ||
    action.artifactType === "failed_action"
  );
}
