import {
  resultCardFromRun,
  type ApiMessage,
  type BacktestJob,
  type BacktestJobResponse,
  type BacktestJobStatus,
  type BacktestRun,
} from "./argus-api";
import { hydrateResultActionsForRun } from "./chat-result-actions";
import {
  nextExperimentRowsFromMetadata,
  type NextExperimentRow,
} from "./chat-next-experiments";
import type { Message } from "@/components/chat/types";
import {
  confirmationStatusFromPayload,
  confirmationStatusLabel,
} from "@/components/chat/confirmation-display";
import type { StrategyConfirmationStatus } from "@/components/chat/types";
import { retainCanonicalResultOwnersForJobUpdate } from "./chat-result-projection-ownership";

export const RESEARCH_JOB_SCOPE = "chat.research";

const TERMINAL_UNSUCCESSFUL_JOB_STATUSES = new Set<BacktestJobStatus>([
  "failed",
  "canceled",
  "expired",
]);
const JOB_SETTLEABLE_CONFIRMATION_STATUSES = new Set<StrategyConfirmationStatus>([
  "ready_to_run",
  "running",
  "request_sent",
  "updated",
]);

export function backtestJobMessageFromApi(message: ApiMessage): Message | null {
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

// Whether a job response still owes the view something. A backtest's result
// is its run; a research job's is the message the response carries, for a
// success (the answer) and for a failure (the persisted note) alike. One null
// response must not end the story: the poll continues, bounded, and the
// card stays pending so reopening the conversation polls again.
export function backtestJobResponseAwaitsPolling(
  response: Pick<BacktestJobResponse, "job" | "run" | "result_message">,
): boolean {
  const job = response.job;
  if (job.status === "queued" || job.status === "running") return true;
  if (job.operation_scope === RESEARCH_JOB_SCOPE) {
    return job.status === "succeeded" && !response.result_message;
  }
  return job.status === "succeeded" && !response.run;
}

// The card-side twin: a research card is pending until its message is in
// the view (recorded on the card by the projection), a backtest card until
// it became a result card.
export function backtestJobCardAwaitsPolling(message: Message): boolean {
  const job = message.backtestJob;
  if (message.kind !== "backtest_job" || !job) return false;
  if (job.status === "queued" || job.status === "running") return true;
  if (job.operation_scope === RESEARCH_JOB_SCOPE) {
    return job.status === "succeeded" && !message.researchResultMessageId;
  }
  return job.status === "succeeded";
}

export function pendingBacktestJobIds(messages: Message[]): string[] {
  const ids = new Set<string>();
  for (const message of messages) {
    if (backtestJobCardAwaitsPolling(message) && message.backtestJob) {
      ids.add(message.backtestJob.id);
    }
  }
  return [...ids];
}

export function applyBacktestJobUpdate(
  messages: Message[],
  response: BacktestJobResponse,
): Message[] {
  const ownerSafeMessages =
    response.job.status === "succeeded" && response.run
      ? retainCanonicalResultOwnersForJobUpdate(
          messages,
          response.job,
          response.run.id,
        )
      : messages;
  const updatedMessages = ownerSafeMessages.map((message) => {
    if (
      message.kind === "backtest_job" &&
      message.backtestJob?.id === response.job.id
    ) {
      if (response.job.status === "succeeded" && response.run) {
        return resultMessageFromRun(
          message,
          response.run,
          response.result_readout,
          nextExperimentRowsFromMetadata({
            next_experiments: response.next_experiments,
          }),
        );
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

export function applyHydratedBacktestJobTruth(messages: Message[]): Message[] {
  return messages.reduce((projected, message) => {
    if (message.kind !== "backtest_job" || !message.backtestJob) {
      return projected;
    }
    return settleConfirmationLabelsForJob(projected, message.backtestJob);
  }, messages);
}

function resultMessageFromRun(
  message: Message,
  run: BacktestRun,
  resultReadout: string | null | undefined,
  nextExperiments?: NextExperimentRow[] | null,
): Message {
  const baseCard = resultCardFromRun(run);
  const actions = hydrateResultActionsForRun(baseCard.actions ?? [], run);
  return {
    ...message,
    kind: "strategy_result",
    content: normalizedReadout(resultReadout) ?? "",
    backtestJob: undefined,
    result: {
      ...baseCard,
      actions,
    },
    actions,
    nextExperiments: nextExperiments ?? undefined,
    artifactId: run.id,
    artifactType: "backtest_run",
    artifactStatus: run.status,
  };
}

function normalizedReadout(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized || null;
}

function settleConfirmationLabelsForJob(
  messages: Message[],
  job: BacktestJob,
): Message[] {
  const status = confirmationStatusForJob(job.status);
  const confirmationMessageId = job.confirmation_message_id?.trim();
  if (!status || !confirmationMessageId) {
    return messages;
  }
  return messages.map((message) => {
    if (
      message.kind !== "strategy_confirmation" ||
      !message.confirmation ||
      message.id !== confirmationMessageId
    ) {
      return message;
    }
    if (
      message.confirmation.confirmation_state !== "superseded" ||
      !JOB_SETTLEABLE_CONFIRMATION_STATUSES.has(
        confirmationStatusFromPayload(message.confirmation),
      )
    ) {
      return message;
    }
    return {
      ...message,
      confirmation: {
        ...message.confirmation,
        status,
        statusLabel: confirmationStatusLabel(status),
      },
    };
  });
}

function confirmationStatusForJob(
  status: BacktestJobStatus,
): StrategyConfirmationStatus | null {
  if (status === "queued" || status === "running") {
    return "request_sent";
  }
  if (status === "failed") {
    // The job card owns the red failure signal; the settled confirmation
    // reads quietly so one failure never paints two alarming pills.
    return "not_completed";
  }
  if (status === "canceled" || status === "expired") {
    return "not_completed";
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
    operation_scope: operationScopeOrNull(record.operation_scope),
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

function operationScopeOrNull(
  value: unknown,
): BacktestJob["operation_scope"] {
  if (
    value === "chat.run_backtest" ||
    value === "backtests.run" ||
    value === RESEARCH_JOB_SCOPE
  ) {
    return value;
  }
  return null;
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
