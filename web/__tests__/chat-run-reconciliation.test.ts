import { describe, expect, test } from "bun:test";

import type { Message } from "../components/chat/types";
import type { BacktestJobResponse } from "../lib/argus-api";
import { pendingBacktestJobIds } from "../lib/chat-backtest-jobs";

type ReconciliationResult =
  | { kind: "durable"; response: BacktestJobResponse }
  | { kind: "replayed" }
  | { kind: "checking"; error: unknown }
  | { kind: "rejected"; error: unknown };

type ReconcileAmbiguousRunResponse = (operations: {
  lookup: () => Promise<BacktestJobResponse>;
  replay: () => Promise<void>;
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

  test("a second 404 stays checking and never triggers a second replay", async () => {
    const reconcile = await loadReconciler();
    let lookupCalls = 0;
    let replayCalls = 0;

    const result = await reconcile({
      lookup: async () => {
        lookupCalls += 1;
        throw statusError(404, "not_found");
      },
      replay: async () => {
        replayCalls += 1;
        throw statusError(0, "stream_interrupted");
      },
    });

    expect(result.kind).toBe("checking");
    expect(lookupCalls).toBe(2);
    expect(replayCalls).toBe(1);
  });

  test("409 or 500 lookup failures never replay the Run action", async () => {
    const reconcile = await loadReconciler();

    for (const status of [409, 500]) {
      let replayCalls = 0;
      const lookupError = statusError(
        status,
        status === 409 ? "idempotency_conflict" : "internal_error",
      );

      const result = await reconcile({
        lookup: async () => {
          throw lookupError;
        },
        replay: async () => {
          replayCalls += 1;
        },
      });

      expect(result).toEqual({ kind: "checking", error: lookupError });
      expect(replayCalls).toBe(0);
    }
  });

  test("a definite replay rejection is preserved without another lookup", async () => {
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

    expect(result).toEqual({ kind: "rejected", error: rejection });
    expect(lookupCalls).toBe(1);
    expect(replayCalls).toBe(1);
  });
});
