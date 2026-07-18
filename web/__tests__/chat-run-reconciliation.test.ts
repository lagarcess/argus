// #242 — ambiguous Run reconciliation resolves from durable truth only.

import { describe, expect, test } from "bun:test";

import {
  isAmbiguousTransportFailure,
  reconcileAmbiguousRun,
  runActionConfirmationId,
} from "@/lib/chat-run-reconciliation";
import { chatStreamIdempotencyKey } from "@/lib/argus-api";
import type { BacktestJobResponse } from "@/lib/argus-types";

const runAction = {
  type: "run_backtest",
  label: "Run backtest",
  payload: { confirmation_id: "confirmation-9" },
} as never;

function jobResponse(status: string, extra: Record<string, unknown> = {}) {
  return {
    job: {
      id: "job-9",
      conversation_id: "conv-9",
      status,
      retryable: false,
      ...extra,
    },
    run: null,
  } as unknown as BacktestJobResponse;
}

describe("runActionConfirmationId", () => {
  test("returns the confirmation id for run actions only", () => {
    expect(runActionConfirmationId(runAction)).toBe("confirmation-9");
    expect(runActionConfirmationId("hola")).toBeNull();
    expect(
      runActionConfirmationId({
        type: "cancel_confirmation",
        payload: { confirmation_id: "confirmation-9" },
      } as never),
    ).toBeNull();
  });
});

describe("chatStreamIdempotencyKey", () => {
  test("run actions reuse confirmation_id so retries share one identity", () => {
    expect(chatStreamIdempotencyKey(runAction)).toBe("confirmation-9");
  });

  test("ordinary messages get a fresh key", () => {
    const first = chatStreamIdempotencyKey("test AAPL");
    const second = chatStreamIdempotencyKey("test AAPL");
    expect(first).not.toBe(second);
  });
});

describe("isAmbiguousTransportFailure", () => {
  test("stream interruptions and fetch exceptions are ambiguous", () => {
    expect(
      isAmbiguousTransportFailure({ status: 0, code: "stream_interrupted" }),
    ).toBe(true);
    expect(isAmbiguousTransportFailure(new TypeError("network"))).toBe(true);
  });

  test("definite HTTP problem responses are not ambiguous", () => {
    expect(isAmbiguousTransportFailure({ status: 429, code: "quota" })).toBe(
      false,
    );
    expect(isAmbiguousTransportFailure({ status: 409 })).toBe(false);
  });
});

describe("reconcileAmbiguousRun", () => {
  test("queued and running jobs stay pending, never terminal", async () => {
    for (const status of ["queued", "running"]) {
      const outcome = await reconcileAmbiguousRun({
        confirmationId: "confirmation-9",
        lookup: async () => jobResponse(status),
      });
      expect(outcome.state).toBe("pending");
    }
  });

  test("succeeded hydrates the canonical response", async () => {
    const outcome = await reconcileAmbiguousRun({
      confirmationId: "confirmation-9",
      lookup: async () => jobResponse("succeeded"),
    });
    expect(outcome.state).toBe("succeeded");
  });

  test("only durable failed/canceled/expired settle as unsuccessful", async () => {
    for (const status of ["failed", "canceled", "expired"]) {
      const outcome = await reconcileAmbiguousRun({
        confirmationId: "confirmation-9",
        lookup: async () =>
          jobResponse(status, { failure_code: "workflow_task_timeout" }),
      });
      expect(outcome.state).toBe("failed");
      if (outcome.state === "failed") {
        expect(outcome.failureCode).toBe("workflow_task_timeout");
      }
    }
  });

  test("404 lookup allows exactly one replay and is not could_not_run", async () => {
    const outcome = await reconcileAmbiguousRun({
      confirmationId: "confirmation-9",
      lookup: async () => {
        throw { status: 404, code: "not_found" };
      },
    });
    expect(outcome).toEqual({ state: "no_reservation", replayAllowed: true });
  });

  test("409 conflict stops automatic replay", async () => {
    const outcome = await reconcileAmbiguousRun({
      confirmationId: "confirmation-9",
      lookup: async () => {
        throw { status: 409, code: "idempotency_conflict" };
      },
    });
    expect(outcome).toEqual({ state: "conflict", replayAllowed: false });
  });

  test("500 integrity failure forbids replaying the Run POST", async () => {
    const outcome = await reconcileAmbiguousRun({
      confirmationId: "confirmation-9",
      lookup: async () => {
        throw { status: 500, code: "internal_error" };
      },
    });
    expect(outcome).toEqual({ state: "unresolved", replayAllowed: false });
  });

  test("a failing lookup transport also resolves nothing", async () => {
    const outcome = await reconcileAmbiguousRun({
      confirmationId: "confirmation-9",
      lookup: async () => {
        throw new TypeError("network down");
      },
    });
    expect(outcome).toEqual({ state: "unresolved", replayAllowed: false });
  });
});
