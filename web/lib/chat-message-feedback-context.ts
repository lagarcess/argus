import type { Message } from "@/components/chat/types";

type FeedbackContextValue = string | number | boolean | null | undefined;

function compactContext(context: Record<string, FeedbackContextValue>) {
  return Object.fromEntries(
    Object.entries(context).filter(
      ([, value]) => value !== null && value !== undefined && value !== "",
    ),
  );
}

export function feedbackContextForMessage(
  message: Message,
  conversationId: string | null | undefined,
  extra: Record<string, FeedbackContextValue> = {},
): Record<string, string | number | boolean> {
  const result = message.result;
  const confirmation = message.confirmation;
  const job = message.backtestJob;
  const artifactId =
    message.artifactId ??
    result?.artifactId ??
    result?.runId ??
    confirmation?.artifactId ??
    confirmation?.confirmation_id ??
    job?.id;
  const artifactType =
    message.artifactType ??
    result?.artifactType ??
    confirmation?.artifactType ??
    (job ? "backtest_job" : undefined);
  const artifactStatus =
    message.artifactStatus ??
    result?.artifactStatus ??
    confirmation?.artifactStatus ??
    job?.status;

  return compactContext({
    message_id: message.id,
    conversation_id: conversationId,
    message_kind: message.kind ?? "text",
    artifact_id: artifactId,
    artifact_type: artifactType,
    artifact_status: artifactStatus,
    result_run_id: result?.runId,
    strategy_id: result?.strategyId,
    saved_strategy_id: message.savedStrategyId ?? result?.savedStrategyId,
    confirmation_id: confirmation?.confirmation_id,
    confirmation_state: confirmation?.confirmation_state,
    confirmation_status: confirmation?.status,
    backtest_job_id: job?.id,
    backtest_job_status: job?.status,
    failure_code: job?.failure_code,
    retryable: job?.retryable,
    ...extra,
  }) as Record<string, string | number | boolean>;
}
