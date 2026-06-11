import { describe, expect, test } from "bun:test";

import { backtestJobCardCopy } from "../lib/backtest-job-card-copy";
import type { BacktestJob } from "../lib/argus-api";

function job(overrides: Partial<BacktestJob> = {}): BacktestJob {
  return {
    id: "job-1",
    conversation_id: "conversation-1",
    request_message_id: "request-message-1",
    confirmation_message_id: "confirmation-message-1",
    status: "failed",
    result_run_id: null,
    failure_code: "market_data_unavailable",
    failure_detail: "market data unavailable",
    retryable: true,
    queued_at: "2026-06-06T12:00:00Z",
    started_at: "2026-06-06T12:00:01Z",
    finished_at: "2026-06-06T12:00:04Z",
    created_at: "2026-06-06T12:00:00Z",
    updated_at: "2026-06-06T12:00:04Z",
    ...overrides,
  };
}

describe("backtest job card copy", () => {
  test("does not promise retry when no retry action is available", () => {
    const copy = backtestJobCardCopy(job({ retryable: true }), {
      canRetry: false,
    });

    expect(copy.bodyKey).toBe("chat.backtest_job.failed_body");
    expect(copy.bodyFallback).not.toContain("retry");
  });

  test("uses retry copy only when the failed job is retryable and action-backed", () => {
    const copy = backtestJobCardCopy(job({ retryable: true }), {
      canRetry: true,
    });

    expect(copy.bodyKey).toBe("chat.backtest_job.failed_retryable_body");
    expect(copy.bodyFallback).toContain("retry");
  });

  test("does not use retry copy for non-retryable failures", () => {
    const copy = backtestJobCardCopy(job({ retryable: false }), {
      canRetry: true,
    });

    expect(copy.bodyKey).toBe("chat.backtest_job.failed_body");
  });

  test("never uses retry copy for canceled or expired jobs", () => {
    expect(
      backtestJobCardCopy(job({ status: "canceled", retryable: true }), {
        canRetry: true,
      }).bodyKey,
    ).toBe("chat.backtest_job.expired_body");

    expect(
      backtestJobCardCopy(job({ status: "expired", retryable: true }), {
        canRetry: true,
      }).bodyKey,
    ).toBe("chat.backtest_job.expired_body");
  });

  test("uses neutral lifecycle tone for completed and not-completed handoff states", () => {
    expect(backtestJobCardCopy(job({ status: "succeeded" })).tone).toBe("neutral");
    expect(backtestJobCardCopy(job({ status: "canceled" })).tone).toBe("neutral");
    expect(backtestJobCardCopy(job({ status: "expired" })).tone).toBe("neutral");
  });
});
