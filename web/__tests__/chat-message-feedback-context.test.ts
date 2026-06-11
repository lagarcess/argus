import { describe, expect, test } from "bun:test";

import { feedbackContextForMessage } from "../lib/chat-message-feedback-context";
import type { Message } from "../components/chat/types";

describe("chat message feedback context", () => {
  test("includes result artifact identifiers for result-card feedback", () => {
    const message: Message = {
      id: "assistant-result-1",
      role: "ai",
      kind: "strategy_result",
      content: "**Quick take**",
      artifactId: "run-1",
      artifactType: "backtest_run",
      artifactStatus: "completed",
      result: {
        strategyName: "AAPL buy and hold",
        period: "June 1, 2025 to June 1, 2026",
        metrics: [],
        runId: "run-1",
        strategyId: "strategy-1",
        savedStrategyId: "strategy-1",
        artifactId: "run-1",
        artifactType: "backtest_run",
        artifactStatus: "completed",
      },
    };

    expect(
      feedbackContextForMessage(message, "conversation-1", {
        rating: "positive",
      }),
    ).toEqual({
      message_id: "assistant-result-1",
      conversation_id: "conversation-1",
      message_kind: "strategy_result",
      artifact_id: "run-1",
      artifact_type: "backtest_run",
      artifact_status: "completed",
      result_run_id: "run-1",
      strategy_id: "strategy-1",
      saved_strategy_id: "strategy-1",
      rating: "positive",
    });
  });

  test("includes job status identifiers for async job feedback", () => {
    const message: Message = {
      id: "assistant-job-1",
      role: "ai",
      kind: "backtest_job",
      artifactId: "job-1",
      artifactType: "backtest_job",
      artifactStatus: "failed",
      backtestJob: {
        id: "job-1",
        conversation_id: "conversation-1",
        request_message_id: "request-message-1",
        confirmation_message_id: "confirmation-message-1",
        status: "failed",
        result_run_id: null,
        failure_code: "market_data_unavailable",
        failure_detail: "market_data_issue",
        retryable: true,
        queued_at: "2026-06-06T12:00:00Z",
        started_at: "2026-06-06T12:00:01Z",
        finished_at: "2026-06-06T12:00:04Z",
        created_at: "2026-06-06T12:00:00Z",
        updated_at: "2026-06-06T12:00:04Z",
      },
    };

    expect(feedbackContextForMessage(message, "conversation-1")).toEqual({
      message_id: "assistant-job-1",
      conversation_id: "conversation-1",
      message_kind: "backtest_job",
      artifact_id: "job-1",
      artifact_type: "backtest_job",
      artifact_status: "failed",
      backtest_job_id: "job-1",
      backtest_job_status: "failed",
      failure_code: "market_data_unavailable",
      retryable: true,
    });
  });

  test("includes confirmation identifiers for confirmation-card feedback", () => {
    const message: Message = {
      id: "assistant-confirmation-1",
      role: "ai",
      kind: "strategy_confirmation",
      artifactId: "confirmation-1",
      artifactType: "confirmation",
      artifactStatus: "active",
      confirmation: {
        confirmation_id: "confirmation-1",
        confirmation_state: "active",
        title: "AAPL buy and hold",
        status: "ready_to_run",
        statusLabel: "Ready to run",
        summary: "Ready to test AAPL.",
        rows: [],
        actions: [],
      },
    };

    expect(feedbackContextForMessage(message, "conversation-1")).toEqual({
      message_id: "assistant-confirmation-1",
      conversation_id: "conversation-1",
      message_kind: "strategy_confirmation",
      artifact_id: "confirmation-1",
      artifact_type: "confirmation",
      artifact_status: "active",
      confirmation_id: "confirmation-1",
      confirmation_state: "active",
      confirmation_status: "ready_to_run",
    });
  });

  test("omits empty optional values", () => {
    const message: Message = {
      id: "assistant-text-1",
      role: "ai",
      kind: "text",
      content: "I can help.",
    };

    expect(feedbackContextForMessage(message, null)).toEqual({
      message_id: "assistant-text-1",
      message_kind: "text",
    });
  });
});
