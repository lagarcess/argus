import type { ApiMessage, BacktestJob } from "./argus-api";
import type { Message } from "@/components/chat/types";
import {
  isHydratableResultCard,
  recordOrNull,
  stringOrNull,
} from "./chat-message-hydration";

type ResultProjectionIdentity = {
  runId: string;
  completedJobId: string | null;
};

function resultProjectionIdentity(
  message: ApiMessage,
): ResultProjectionIdentity | null {
  if (message.role === "user") return null;
  const metadata = message.metadata ?? {};
  if (!isHydratableResultCard(metadata.result_card)) return null;
  const runId =
    stringOrNull(metadata.result_run_id) ??
    stringOrNull(metadata.latest_run_id);
  if (!runId) return null;
  const backtestJob = recordOrNull(metadata.backtest_job);
  const backtestJobId =
    stringOrNull(metadata.backtest_job_id) ??
    stringOrNull(backtestJob?.id);
  const completedJobRunId = stringOrNull(backtestJob?.result_run_id);
  return {
    runId,
    completedJobId:
      backtestJobId !== null &&
      backtestJob?.status === "succeeded" &&
      completedJobRunId === runId
        ? backtestJobId
        : null,
  };
}

/**
 * One canonical result message owns each hydrated result surface.
 *
 * A completed-job projection is a reload fallback for a missing result message.
 * When the API also returns the durable result-bearing message for the same run,
 * that durable message owns the card and the job projection is only an alias.
 */
export function retainCanonicalResultProjectionOwners(
  messages: ApiMessage[],
): ApiMessage[] {
  const durableResultRunIds = new Set(
    messages
      .map(resultProjectionIdentity)
      .filter(
        (
          identity,
        ): identity is ResultProjectionIdentity =>
          identity !== null && identity.completedJobId === null,
      )
      .map((identity) => identity.runId),
  );
  const fallbackOwnerByRunId = new Map<
    string,
    { jobId: string; messageId: string }
  >();
  // Recovery aliases carry the same canonical run truth. Stable job/message
  // identities choose one fallback owner without depending on API or DOM order.
  for (const message of messages) {
    const identity = resultProjectionIdentity(message);
    if (
      identity === null ||
      identity.completedJobId === null ||
      durableResultRunIds.has(identity.runId)
    ) {
      continue;
    }
    const current = fallbackOwnerByRunId.get(identity.runId);
    if (
      current === undefined ||
      identity.completedJobId < current.jobId ||
      (identity.completedJobId === current.jobId &&
        message.id < current.messageId)
    ) {
      fallbackOwnerByRunId.set(identity.runId, {
        jobId: identity.completedJobId,
        messageId: message.id,
      });
    }
  }

  return messages.filter((message) => {
    const identity = resultProjectionIdentity(message);
    if (identity === null || identity.completedJobId === null) return true;
    const fallbackOwner = fallbackOwnerByRunId.get(identity.runId);
    return (
      fallbackOwner?.jobId === identity.completedJobId &&
      fallbackOwner.messageId === message.id
    );
  });
}

/**
 * Keep the durable result message as the result owner when polling resolves a
 * completed job alias. Without a durable result, one stable job-message alias
 * remains available for promotion into the completed-result fallback.
 */
export function retainCanonicalResultOwnersForJobUpdate(
  messages: Message[],
  job: BacktestJob,
  runId: string,
): Message[] {
  if (job.status !== "succeeded") return messages;

  const matchingJobAliases = messages.filter(
    (message) =>
      message.kind === "backtest_job" &&
      message.backtestJob?.id === job.id,
  );
  if (matchingJobAliases.length === 0) return messages;

  const durableResultExists = messages.some(
    (message) =>
      message.kind === "strategy_result" && message.result?.runId === runId,
  );
  const fallbackOwnerMessageId = durableResultExists
    ? null
    : matchingJobAliases.reduce<string | null>(
        (ownerId, message) =>
          ownerId === null || message.id < ownerId ? message.id : ownerId,
        null,
      );

  return messages.filter(
    (message) =>
      message.kind !== "backtest_job" ||
      message.backtestJob?.id !== job.id ||
      message.id === fallbackOwnerMessageId,
  );
}
