import {
  resultCardFromRun,
  type ApiMessage,
  type BacktestJob,
  type BacktestJobResponse,
  type BacktestJobStatus,
  type BacktestRun,
} from "./argus-api";
import { hydrateResultActionsForRun } from "./chat-result-actions";
import type { Message } from "@/components/chat/types";

const ACTIVE_JOB_STATUSES = new Set<BacktestJobStatus>([
  "queued",
  "running",
  "succeeded",
]);

const TERMINAL_UNSUCCESSFUL_JOB_STATUSES = new Set<BacktestJobStatus>([
  "failed",
  "canceled",
  "expired",
]);

export function backtestJobMessageFromApi(message: ApiMessage): Message | null {
  if (message.role === "user") {
    return null;
  }
  const job = backtestJobFromMetadata(message.metadata ?? {});
  if (!job) {
    return null;
  }
  return {
    id: message.id,
    role: "ai",
    kind: "backtest_job",
    content: message.content,
    backtestJob: job,
    artifactId: job.id,
    artifactType: "backtest_job",
    artifactStatus: job.status,
  };
}

export function backtestJobFromFinalPayload(
  payload: Record<string, unknown>,
): BacktestJob | null {
  return backtestJobFromUnknown(payload.backtest_job);
}

export function backtestJobFromMetadata(
  metadata: Record<string, unknown>,
): BacktestJob | null {
  return backtestJobFromUnknown(metadata.backtest_job);
}

export function pendingBacktestJobIds(messages: Message[]): string[] {
  const ids = new Set<string>();
  for (const message of messages) {
    const job = message.backtestJob;
    if (message.kind !== "backtest_job" || !job) {
      continue;
    }
    if (ACTIVE_JOB_STATUSES.has(job.status)) {
      ids.add(job.id);
    }
  }
  return [...ids];
}

export function applyBacktestJobUpdate(
  messages: Message[],
  response: BacktestJobResponse,
): Message[] {
  const updatedMessages = messages.map((message) => {
    if (
      message.kind === "backtest_job" &&
      message.backtestJob?.id === response.job.id
    ) {
      if (response.job.status === "succeeded" && response.run) {
        return resultMessageFromRun(message, response.run);
      }
      return {
        ...message,
        backtestJob: response.job,
        artifactStatus: response.job.status,
      };
    }
    return message;
  });
  return settleConfirmationLabelsForJob(updatedMessages, response.job);
}

function resultMessageFromRun(message: Message, run: BacktestRun): Message {
  const baseCard = resultCardFromRun(run);
  const actions = hydrateResultActionsForRun(baseCard.actions ?? [], run);
  return {
    ...message,
    kind: "strategy_result",
    content: message.content,
    backtestJob: undefined,
    result: {
      ...baseCard,
      actions,
    },
    actions,
    artifactId: run.id,
    artifactType: "backtest_run",
    artifactStatus: run.status,
  };
}

function settleConfirmationLabelsForJob(
  messages: Message[],
  job: BacktestJob,
): Message[] {
  const statusLabel = confirmationStatusLabelForJob(job.status);
  if (!statusLabel) {
    return messages;
  }
  return messages.map((message) => {
    if (message.kind !== "strategy_confirmation" || !message.confirmation) {
      return message;
    }
    if (
      message.confirmation.confirmation_state !== "superseded" ||
      message.confirmation.statusLabel !== "Running"
    ) {
      return message;
    }
    return {
      ...message,
      confirmation: {
        ...message.confirmation,
        statusLabel,
      },
    };
  });
}

function confirmationStatusLabelForJob(status: BacktestJobStatus): string | null {
  if (status === "failed") {
    return "Could not run";
  }
  if (status === "canceled" || status === "expired") {
    return "Not completed";
  }
  return null;
}

function backtestJobFromUnknown(value: unknown): BacktestJob | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = stringOrNull(record.id);
  const conversationId = stringOrNull(record.conversation_id);
  const status = backtestJobStatusOrNull(record.status);
  if (!id || !conversationId || !status) {
    return null;
  }
  return {
    id,
    conversation_id: conversationId,
    request_message_id: stringOrNull(record.request_message_id),
    confirmation_message_id: stringOrNull(record.confirmation_message_id),
    status,
    result_run_id: stringOrNull(record.result_run_id),
    failure_code: stringOrNull(record.failure_code),
    failure_detail: stringOrNull(record.failure_detail),
    retryable: Boolean(record.retryable),
    queued_at: stringOrNull(record.queued_at),
    started_at: stringOrNull(record.started_at),
    finished_at: stringOrNull(record.finished_at),
    created_at: stringOrNull(record.created_at),
    updated_at: stringOrNull(record.updated_at),
  };
}

function backtestJobStatusOrNull(value: unknown): BacktestJobStatus | null {
  if (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "canceled" ||
    value === "expired"
  ) {
    return value;
  }
  return null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function isTerminalBacktestJobStatus(status: BacktestJobStatus): boolean {
  return (
    status === "succeeded" || TERMINAL_UNSUCCESSFUL_JOB_STATUSES.has(status)
  );
}
