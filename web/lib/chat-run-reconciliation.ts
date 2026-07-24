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
  getBacktestJob,
  type BacktestJobResponse,
} from "@/lib/argus-api";
import {
  applyBacktestJobUpdate,
  pendingBacktestJobIds,
} from "@/lib/chat-backtest-jobs";
import { normalizeDurableRetryActionHistory } from "@/lib/chat-retry-actions";

type ReconciliationResult =
  | { kind: "durable"; response: BacktestJobResponse }
  | { kind: "replayed" }
  | { kind: "checking"; error: unknown }
  | { kind: "rejected"; error: unknown };

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
}): Promise<ReconciliationResult> {
  try {
    return { kind: "durable", response: await operations.lookup() };
  } catch (lookupError) {
    if (errorStatus(lookupError) !== 404) {
      return { kind: "checking", error: lookupError };
    }
  }

  try {
    await operations.replay();
    return { kind: "replayed" };
  } catch (replayError) {
    if (!isTransportAmbiguity(replayError)) {
      return { kind: "rejected", error: replayError };
    }
    try {
      return { kind: "durable", response: await operations.lookup() };
    } catch (lookupError) {
      return { kind: "checking", error: lookupError };
    }
  }
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
  }, [applyResponse, pendingBacktestJobKey]);
}

function errorStatus(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

function isTransportAmbiguity(error: unknown): boolean {
  const status = errorStatus(error);
  return status === null || status === 0;
}
