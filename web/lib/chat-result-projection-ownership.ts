import type { ApiMessage } from "./argus-api";
import {
  isHydratableResultCard,
  recordOrNull,
  stringOrNull,
} from "./chat-message-hydration";

type ResultProjectionIdentity = {
  runId: string;
  isCompletedJobProjection: boolean;
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
    isCompletedJobProjection:
      backtestJobId !== null &&
      backtestJob?.status === "succeeded" &&
      completedJobRunId === runId,
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
          identity !== null && !identity.isCompletedJobProjection,
      )
      .map((identity) => identity.runId),
  );

  return messages.filter((message) => {
    const identity = resultProjectionIdentity(message);
    return !(
      identity?.isCompletedJobProjection &&
      durableResultRunIds.has(identity.runId)
    );
  });
}
