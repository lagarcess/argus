import { describe, expect, test } from "bun:test";

import type { Message } from "../components/chat/types";
import type { BacktestJobResponse } from "../lib/argus-api";
import { pendingBacktestJobIds } from "../lib/chat-backtest-jobs";

type ReconciliationResult =
  | { kind: "durable"; response: BacktestJobResponse }
  | { kind: "replayed" }
  | { kind: "recoverable"; error: unknown };

type ReconcileAmbiguousRunResponse = (operations: {
  lookup: () => Promise<BacktestJobResponse>;
  replay: () => Promise<void>;
  pause?: (delayMs: number) => Promise<void>;
}) => Promise<ReconciliationResult>;

async function loadReconciler(): Promise<ReconcileAmbiguousRunResponse> {
  const modulePath = "../lib/chat-run-reconciliation";
  const reconciliationModule = await import(modulePath).catch(() => null);
  expect(reconciliationModule).not.toBeNull();
  const reconcile = reconciliationModule?.reconcileAmbiguousRunResponse;
  expect(typeof reconcile).toBe("function");
  return reconcile as ReconcileAmbiguousRunResponse;
}

function queuedResponse(): BacktestJobResponse {
  return {
    job: {
      id: "job-1",
      conversation_id: "conversation-1",
      confirmation_message_id: "confirmation-message-1",
      status: "queued",
      result_run_id: null,
      retryable: false,
    },
    run: null,
  };
}

function statusError(status: number, code: string): Error & {
  status: number;
  code: string;
} {
  return Object.assign(new Error(code), { status, code });
}

describe("ambiguous Run response reconciliation", () => {
  test("only an ambiguous Run exception carries its confirmation identity", async () => {
    const modulePath = "../lib/chat-run-reconciliation";
    const reconciliationModule = await import(modulePath);
    const confirmationId =
      reconciliationModule.ambiguousRunConfirmationId;
    expect(typeof confirmationId).toBe("function");
    const runAction = {
      type: "run_backtest",
      payload: { confirmation_id: " confirmation-1 " },
    };

    expect(confirmationId(runAction, statusError(0, "interrupted"))).toBe(
      "confirmation-1",
    );
    expect(confirmationId(runAction, new TypeError("fetch failed"))).toBe(
      "confirmation-1",
    );
    expect(confirmationId(runAction, statusError(500, "internal_error"))).toBeNull();
    expect(
      confirmationId(
        { type: "change_dates", payload: runAction.payload },
        statusError(0, "interrupted"),
      ),
    ).toBeNull();
  });

  test("durable queued truth replaces the placeholder with a pollable job", async () => {
    const modulePath = "../lib/chat-run-reconciliation";
    const reconciliationModule = await import(modulePath).catch(() => null);
    expect(reconciliationModule).not.toBeNull();
    const applyResponse =
      reconciliationModule?.applyReconciledBacktestJobResponse;
    expect(typeof applyResponse).toBe("function");
    const messages: Message[] = [
      {
        id: "assistant-placeholder",
        role: "ai",
        kind: "text",
        content: "",
      },
    ];

    const updated = applyResponse(
      messages,
      queuedResponse(),
      "assistant-placeholder",
    ) as Message[];

    expect(updated[0]?.kind).toBe("backtest_job");
    expect(updated[0]?.backtestJob?.status).toBe("queued");
    expect(pendingBacktestJobIds(updated)).toEqual(["job-1"]);
  });

  test("queued durable truth returns without replay", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const response = queuedResponse();

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        return response;
      },
      replay: async () => {
        replayCalls += 1;
      },
    });

    expect(result).toEqual({ kind: "durable", response });
    expect(lookupCalls).toBe(1);
    expect(replayCalls).toBe(0);
  });

  test("404 permits one replay and an ambiguous replay performs one relookup", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const response = queuedResponse();

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        if (lookupCalls === 1) {
          throw statusError(404, "not_found");
        }
        return response;
      },
      replay: async () => {
        replayCalls += 1;
        throw statusError(0, "stream_interrupted");
      },
    });

    expect(result).toEqual({ kind: "durable", response });
    expect(lookupCalls).toBe(2);
    expect(replayCalls).toBe(1);
  });

  test("a second 404 exits through bounded recovery and never triggers a second replay", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const pauses: number[] = [];

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        throw statusError(404, "not_found");
      },
      replay: async () => {
        replayCalls += 1;
        throw statusError(0, "stream_interrupted");
      },
      pause: async (delayMs) => {
        pauses.push(delayMs);
      },
    });

    expect(result.kind).toBe("recoverable");
    expect(lookupCalls).toBe(3);
    expect(replayCalls).toBe(1);
    expect(pauses).toEqual([250, 750]);
  });

  test("409 lookup stops immediately with typed recovery and never replays", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const lookupError = statusError(409, "idempotency_conflict");

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        throw lookupError;
      },
      replay: async () => {
        replayCalls += 1;
      },
      pause: async () => {
        throw new Error("409 must not continue automatic lookup");
      },
    });

    expect(result).toEqual({ kind: "recoverable", error: lookupError });
    expect(lookupCalls).toBe(1);
    expect(replayCalls).toBe(0);
  });

  test("500 lookup uses a finite lookup-only continuation and never replays", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const pauses: number[] = [];
    const lookupError = statusError(500, "internal_error");

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        throw lookupError;
      },
      replay: async () => {
        replayCalls += 1;
      },
      pause: async (delayMs) => {
        pauses.push(delayMs);
      },
    });

    expect(result).toEqual({ kind: "recoverable", error: lookupError });
    expect(lookupCalls).toBe(3);
    expect(replayCalls).toBe(0);
    expect(pauses).toEqual([250, 750]);
  });

  test("a definite stale replay rejection is preserved without another lookup", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const rejection = statusError(409, "confirmation_required");

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        throw statusError(404, "not_found");
      },
      replay: async () => {
        replayCalls += 1;
        throw rejection;
      },
    });

    expect(result).toEqual({ kind: "recoverable", error: rejection });
    expect(lookupCalls).toBe(1);
    expect(replayCalls).toBe(1);
  });

  test("an in-progress replay rejection relooks up the racing durable job", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;
    const response = queuedResponse();

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        if (lookupCalls === 1) {
          throw statusError(404, "not_found");
        }
        return response;
      },
      replay: async () => {
        replayCalls += 1;
        throw statusError(409, "idempotency_in_progress");
      },
      pause: async () => undefined,
    });

    expect(result).toEqual({ kind: "durable", response });
    expect(lookupCalls).toBe(2);
    expect(replayCalls).toBe(1);
  });

  test("recoverable ambiguity renders existing typed recovery without could_not_run", async () => {
    const modulePath = "../lib/chat-run-reconciliation";
    const reconciliationModule = await import(modulePath);
    const applyRecovery =
      reconciliationModule.applyRecoverableRunReconciliation;
    expect(typeof applyRecovery).toBe("function");
    const messages: Message[] = [
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "superseded",
          title: "AAPL buy and hold",
          status: "running",
          statusLabel: "Running",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
      },
      {
        id: "assistant-placeholder",
        role: "ai",
        kind: "text",
        content: "",
      },
    ];

    const updated = applyRecovery(
      messages,
      "assistant-placeholder",
      "conversation-1",
      statusError(409, "idempotency_conflict"),
    ) as Message[];

    expect(updated[0]?.confirmation?.status).toBe("running");
    expect(updated[0]?.confirmation?.status).not.toBe("could_not_run");
    expect(updated[1]?.recoveryDisplay).toEqual({
      kind: "artifact_action_recovery",
      status: "invalid_state",
    });
    expect(updated[1]?.actions?.map((action) => action.type)).toEqual([
      "retry_load_conversation",
    ]);
  });
});
