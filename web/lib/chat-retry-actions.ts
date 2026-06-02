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
  return {
    id: `retry-failed-action-${artifactId ?? "latest"}`,
    label: "Retry",
    labelKey: "common.retry",
    value: "Retry",
    type: "retry_failed_action",
    artifactId: artifactId ?? undefined,
    artifactType: "failed_action",
    artifactStatus: failedAction.artifactStatus ?? "failed",
    payload: {
      failed_action_id: artifactId,
    },
  };
}

export function retryLastTurnActionFromMessage(
  message: string,
): ChatActionOption | null {
  const trimmed = message.trim();
  if (!trimmed) {
    return null;
  }
  return {
    id: "retry-last-turn",
    label: "Retry",
    labelKey: "common.retry",
    value: "Retry",
    type: "retry_last_turn",
    payload: {
      message: trimmed,
    },
  };
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

export function isRetryAction(action: ChatActionOption | null | undefined): boolean {
  if (!action) {
    return false;
  }
  return (
    action.type === "retry_failed_action" ||
    action.type === "retry_last_turn" ||
    action.artifactType === "failed_action"
  );
}
