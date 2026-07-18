// #242 — ambiguous Run reconciliation from durable backend truth.
//
// A lost HTTP/SSE response is transport ambiguity, never a business failure.
// The client shows a typed checking presentation while it reads durable truth
// through GET /backtest-jobs/by-action/{confirmation_id}; only durable
// failed/canceled/expired state may settle the confirmation as unsuccessful,
// and a timeout, disconnect, fetch exception, or 404 lookup alone must never
// produce could_not_run.

import type { BacktestJobResponse, ChatActionRequest } from "@/lib/argus-api";

export type RunReconciliationOutcome =
  | { state: "pending"; jobId: string }
  | { state: "succeeded"; response: BacktestJobResponse }
  | {
      state: "failed";
      failureCode: string | null;
      retryable: boolean;
    }
  | { state: "no_reservation"; replayAllowed: true }
  | { state: "conflict"; replayAllowed: false }
  | { state: "unresolved"; replayAllowed: false };

export function chatStreamIdempotencyKey(
  input: string | ChatActionRequest,
): string {
  if (typeof input !== "string" && input.type === "run_backtest") {
    const payload = (input.payload ?? {}) as { confirmation_id?: unknown };
    const confirmationId =
      typeof payload.confirmation_id === "string"
        ? payload.confirmation_id.trim()
        : "";
    // Contract: the Run action identity is its confirmation_id, so retry,
    // reconnect, and reload reuse the same approved reservation.
    if (confirmationId) return confirmationId;
  }
  return crypto.randomUUID();
}

export function runActionConfirmationId(
  input: string | ChatActionRequest | undefined,
): string | null {
  if (!input || typeof input === "string") return null;
  if (input.type !== "run_backtest") return null;
  const payload = (input.payload ?? {}) as { confirmation_id?: unknown };
  const confirmationId =
    typeof payload.confirmation_id === "string"
      ? payload.confirmation_id.trim()
      : "";
  return confirmationId || null;
}

export function isAmbiguousTransportFailure(error: unknown): boolean {
  if (!error || typeof error !== "object") return true;
  const status = (error as { status?: unknown }).status;
  const code = (error as { code?: unknown }).code;
  if (code === "stream_interrupted") return true;
  // A definite HTTP problem response is not ambiguity — durable truth spoke.
  if (typeof status === "number" && status >= 400) return false;
  return true;
}

export type AmbiguousRunSettlementDeps = {
  confirmationId: string;
  lookup: (confirmationId: string) => Promise<BacktestJobResponse>;
  replay: () => Promise<void>;
  notify: (
    key:
      | "checking"
      | "pending"
      | "recovered"
      | "failed"
      | "conflict"
      | "unresolved",
  ) => void;
  renderDurableTruth: () => Promise<void>;
};

// Full settlement flow for an ambiguous Run transport failure: typed checking
// presentation, at most one same-identity replay when no reservation exists,
// then rendering durable backend truth instead of inventing terminal state.
export async function settleAmbiguousRun(
  deps: AmbiguousRunSettlementDeps,
): Promise<boolean> {
  deps.notify("checking");
  const outcome = await reconcileAmbiguousRun({
    confirmationId: deps.confirmationId,
    lookup: deps.lookup,
  });
  if (outcome.state === "no_reservation") {
    try {
      await deps.replay();
      return true;
    } catch {
      deps.notify("unresolved");
    }
  } else if (outcome.state === "pending") {
    deps.notify("pending");
  } else if (outcome.state === "succeeded") {
    deps.notify("recovered");
  } else if (outcome.state === "failed") {
    deps.notify("failed");
  } else if (outcome.state === "conflict") {
    deps.notify("conflict");
  } else {
    deps.notify("unresolved");
  }
  await deps.renderDurableTruth();
  return true;
}

export async function reconcileAmbiguousRun(options: {
  confirmationId: string;
  lookup: (confirmationId: string) => Promise<BacktestJobResponse>;
}): Promise<RunReconciliationOutcome> {
  let response: BacktestJobResponse;
  try {
    response = await options.lookup(options.confirmationId);
  } catch (error) {
    const status = (error as { status?: unknown }).status;
    if (status === 404) {
      // No reservation exists: the original action may be replayed once with
      // the same key; atomic admission returns the racing job or admits one.
      return { state: "no_reservation", replayAllowed: true };
    }
    if (status === 409) {
      return { state: "conflict", replayAllowed: false };
    }
    // 500 integrity failures and repeated transport failures resolve nothing;
    // the client must not replay the Run POST.
    return { state: "unresolved", replayAllowed: false };
  }

  const status = String(response.job?.status ?? "").toLowerCase();
  if (status === "succeeded") {
    return { state: "succeeded", response };
  }
  if (status === "failed" || status === "canceled" || status === "expired") {
    return {
      state: "failed",
      failureCode: response.job?.failure_code ?? null,
      retryable: Boolean(response.job?.retryable),
    };
  }
  return { state: "pending", jobId: String(response.job?.id ?? "") };
}
