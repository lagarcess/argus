import {
  useCallback,
  useEffect,
  useMemo,
  type Dispatch,
  type SetStateAction,
} from "react";

import type { ChatActionOption, Message } from "@/components/chat/types";
import { normalizeConfirmationHistory } from "@/components/chat/artifact-history";
import {
  apiFetch,
  ChatStreamError,
  getBacktestJob,
  type BacktestJobResponse,
  type ChatStreamEvent,
} from "@/lib/argus-api";
import {
  applyBacktestJobUpdate,
  pendingBacktestJobIds,
} from "@/lib/chat-backtest-jobs";
import {
  conversationLoadRetryActionFromConversationId,
  normalizeDurableRetryActionHistory,
} from "@/lib/chat-retry-actions";

type ReconciliationResult =
  | { kind: "durable"; response: BacktestJobResponse }
  | { kind: "replayed" }
  | { kind: "recoverable"; error: unknown };

const LOOKUP_RETRY_DELAYS_MS = [250, 750] as const;

export function throwIfAmbiguousRunSseError(
  event: ChatStreamEvent,
  runAction: boolean,
): void {
  if (!runAction || event.event !== "error") return;
  throw new ChatStreamError(
    event.data.detail,
    0,
    event.data.code ?? "run_replay_sse_error",
  );
}

export function throwIfAmbiguousRunStreamTermination(
  runAction: boolean,
  finalSeen: boolean,
): void {
  if (!runAction || finalSeen) return;
  throw new ChatStreamError(
    "The Run response ended before durable status was confirmed.",
    0,
    "run_stream_ended_ambiguously",
  );
}

export async function getBacktestJobByAction(
  confirmationId: string,
): Promise<BacktestJobResponse> {
  return apiFetch<BacktestJobResponse>(
    `/backtest-jobs/by-action/${encodeURIComponent(confirmationId)}`,
  );
}

export async function reconcileAmbiguousRunResponse(operations: {
  lookup: () => Promise<BacktestJobResponse>;
  replay: () => Promise<void>;
  pause?: (delayMs: number) => Promise<void>;
}): Promise<ReconciliationResult> {
  try {
    return { kind: "durable", response: await operations.lookup() };
  } catch (lookupError) {
    const status = errorStatus(lookupError);
    if (status === 409 || (status !== null && status < 500 && status !== 404)) {
      return { kind: "recoverable", error: lookupError };
    }
    if (status !== 404) {
      return continueDurableRunLookup(operations, lookupError);
    }
  }

  try {
    await operations.replay();
    return { kind: "replayed" };
  } catch (replayError) {
    if (
      isTransportAmbiguity(replayError) ||
      errorStatus(replayError) === 500 ||
      errorCode(replayError) === "idempotency_in_progress"
    ) {
      return continueDurableRunLookup(operations, replayError);
    }
    return { kind: "recoverable", error: replayError };
  }
}

async function continueDurableRunLookup(
  operations: {
    lookup: () => Promise<BacktestJobResponse>;
    pause?: (delayMs: number) => Promise<void>;
  },
  initialError: unknown,
): Promise<ReconciliationResult> {
  const pause = operations.pause ?? waitForLookupRetry;
  let latestError = initialError;
  for (const delayMs of LOOKUP_RETRY_DELAYS_MS) {
    await pause(delayMs);
    try {
      return { kind: "durable", response: await operations.lookup() };
    } catch (lookupError) {
      latestError = lookupError;
      if (errorStatus(lookupError) === 409) {
        break;
      }
    }
  }
  return { kind: "recoverable", error: latestError };
}

function waitForLookupRetry(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}

export function applyRecoverableRunReconciliation(
  messages: Message[],
  assistantId: string,
  conversationId: string,
  error: unknown,
): Message[] {
  const retryAction =
    conversationLoadRetryActionFromConversationId(conversationId);
  const recoveryDisplay =
    errorStatus(error) === 409
      ? {
          kind: "artifact_action_recovery" as const,
          status: "invalid_state",
        }
      : {
          kind: "recovery_code" as const,
          code: "runtime_failure",
        };
  return messages.map((message) =>
    message.id === assistantId
      ? {
          ...message,
          content: "",
          recoveryDisplay,
          actions: retryAction ? [retryAction] : undefined,
        }
      : message,
  );
}

export function ambiguousRunConfirmationId(
  action: ChatActionOption | undefined,
  error: unknown,
): string | null {
  if (action?.type !== "run_backtest" || !isTransportAmbiguity(error)) {
    return null;
  }
  const confirmationId = action.payload?.confirmation_id;
  return typeof confirmationId === "string" && confirmationId.trim()
    ? confirmationId.trim()
    : null;
}

export function applyReconciledBacktestJobResponse(
  messages: Message[],
  response: BacktestJobResponse,
  assistantId: string,
): Message[] {
  const pollableMessages = messages.map((message) =>
    message.id === assistantId
      ? {
          ...message,
          kind: "backtest_job" as const,
          backtestJob: response.job,
          artifactId: response.job.id,
          artifactType: "backtest_job" as const,
          artifactStatus: response.job.status,
        }
      : message,
  );
  return applyBacktestJobUpdate(pollableMessages, response);
}

export function useBacktestJobPolling(
  messages: Message[],
  ownsConversation: (conversationId?: string | null) => boolean,
  setMessages: Dispatch<SetStateAction<Message[]>>,
  onDurableCompletion?: (response: BacktestJobResponse) => void,
): void {
  const pendingBacktestJobKey = useMemo(
    () => pendingBacktestJobIds(messages).join("|"),
    [messages],
  );
  const applyResponse = useCallback(
    (response: BacktestJobResponse) => {
      if (!ownsConversation(response.job.conversation_id)) return;
      setMessages((current) =>
        normalizeDurableRetryActionHistory(
          normalizeConfirmationHistory(
            applyBacktestJobUpdate(current, response),
          ),
        ),
      );
    },
    [ownsConversation, setMessages],
  );
  useEffect(() => {
    if (!pendingBacktestJobKey) return;
    let cancelled = false;
    const timers: number[] = [];

    const pollJob = async (jobId: string, attempt = 0) => {
      try {
        const response = await getBacktestJob(jobId);
        if (cancelled) return;
        applyResponse(response);
        const shouldContinue =
          response.job.status === "queued" ||
          response.job.status === "running" ||
          (response.job.status === "succeeded" && !response.run);
        if (!shouldContinue) {
          onDurableCompletion?.(response);
        }
        if (shouldContinue && attempt < 45) {
          timers.push(
            window.setTimeout(() => void pollJob(jobId, attempt + 1), 2000),
          );
        }
      } catch {
        if (!cancelled && attempt < 5) {
          timers.push(
            window.setTimeout(() => void pollJob(jobId, attempt + 1), 3000),
          );
        }
      }
    };

    pendingBacktestJobKey
      .split("|")
      .filter(Boolean)
      .forEach((jobId) => void pollJob(jobId));

    return () => {
      cancelled = true;
      timers.forEach(window.clearTimeout);
    };
  }, [applyResponse, onDurableCompletion, pendingBacktestJobKey]);
}

function errorStatus(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

function errorCode(error: unknown): string | null {
  if (typeof error !== "object" || error === null) return null;
  const code = (error as { code?: unknown }).code;
  return typeof code === "string" ? code : null;
}

function isTransportAmbiguity(error: unknown): boolean {
  const status = errorStatus(error);
  return status === null || status === 0;
}
