import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  normalizeConfirmationHistory,
  supersedePriorConfirmations,
} from "../components/chat/artifact-history";
import {
  applyBacktestJobUpdate,
  backtestJobFromFinalPayload,
  backtestJobMessageFromApi,
  pendingBacktestJobIds,
} from "../lib/chat-backtest-jobs";
import type { ApiMessage, BacktestJob, BacktestRun } from "../lib/argus-api";
import type { Message } from "../components/chat/types";

const root = join(import.meta.dir, "..");

function job(overrides: Partial<BacktestJob> = {}): BacktestJob {
  return {
    id: "job-1",
    conversation_id: "conversation-1",
    request_message_id: "request-message-1",
    confirmation_message_id: "confirmation-message-1",
    status: "queued",
    result_run_id: null,
    failure_code: null,
    failure_detail: null,
    retryable: false,
    queued_at: "2026-06-06T12:00:00Z",
    started_at: null,
    finished_at: null,
    created_at: "2026-06-06T12:00:00Z",
    updated_at: "2026-06-06T12:00:00Z",
    ...overrides,
  };
}

function run(): BacktestRun {
  return {
    id: "run-1",
    conversation_id: "conversation-1",
    strategy_id: null,
    status: "completed",
    asset_class: "equity",
    symbols: ["AAPL"],
    allocation_method: "equal_weight",
    benchmark_symbol: "SPY",
    metrics: {
      aggregate: { performance: { total_return_pct: 12.4 } },
      by_symbol: {},
    },
    config_snapshot: { template: "buy_and_hold", benchmark_symbol: "SPY" },
    conversation_result_card: {
      title: "AAPL buy and hold",
      symbols: ["AAPL"],
      date_range: {
        start: "2025-06-06",
        end: "2026-06-06",
        display: "June 6, 2025 to June 6, 2026",
      },
      status_label: "Simulation Complete",
      rows: [
        {
          key: "total_return_pct",
          label: "Total return",
          value: "+12.4%",
        },
      ],
      assumptions: ["Long-only", "Benchmark: SPY"],
      actions: [
        {
          type: "show_breakdown",
          label: "Show a breakdown",
          presentation: "result",
          payload: {},
        },
      ],
      chart: null,
    },
    chart: null,
    trades: [],
    created_at: "2026-06-06T12:00:04Z",
  };
}

function apiMessageWithJob(currentJob: BacktestJob): ApiMessage {
  return {
    id: "assistant-job-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content:
      "I started the backtest. I will show the result here as soon as it is ready.",
    created_at: "2026-06-06T12:00:00Z",
    metadata: {
      backtest_job: currentJob,
      backtest_job_id: currentJob.id,
    },
  };
}

function queuedJobMessage(): Message {
  const message = backtestJobMessageFromApi(apiMessageWithJob(job()));
  if (!message) {
    throw new Error("Expected hydrated backtest job message.");
  }
  return message;
}

describe("chat backtest jobs", () => {
  test("hydrates persisted job metadata into a durable job message", () => {
    const message = backtestJobMessageFromApi(apiMessageWithJob(job()));

    expect(message?.kind).toBe("backtest_job");
    expect(message?.backtestJob?.id).toBe("job-1");
    expect(message?.backtestJob?.status).toBe("queued");
    expect(pendingBacktestJobIds([message!])).toEqual(["job-1"]);
  });

  test("hydrates stream final job payloads into durable job state", () => {
    const currentJob = job({ status: "running" });
    const message = backtestJobFromFinalPayload({ backtest_job: currentJob });

    expect(message?.id).toBe("job-1");
    expect(message?.status).toBe("running");
    expect(pendingBacktestJobIds([{ ...queuedJobMessage(), backtestJob: message! }])).toEqual([
      "job-1",
    ]);
  });

  test("pending job ids keep queued running and succeeded-without-run pollable", () => {
    const messages: Message[] = [
      { ...queuedJobMessage(), id: "queued", backtestJob: job({ id: "queued", status: "queued" }) },
      { ...queuedJobMessage(), id: "running", backtestJob: job({ id: "running", status: "running" }) },
      { ...queuedJobMessage(), id: "succeeded", backtestJob: job({ id: "succeeded", status: "succeeded" }) },
      { ...queuedJobMessage(), id: "failed", backtestJob: job({ id: "failed", status: "failed" }) },
      { ...queuedJobMessage(), id: "canceled", backtestJob: job({ id: "canceled", status: "canceled" }) },
      { ...queuedJobMessage(), id: "expired", backtestJob: job({ id: "expired", status: "expired" }) },
    ];

    expect(pendingBacktestJobIds(messages)).toEqual([
      "queued",
      "running",
      "succeeded",
    ]);
  });

  test("failed durable job update replaces a local running state", () => {
    const running: Message = {
      ...queuedJobMessage(),
      backtestJob: job({ status: "running", started_at: "2026-06-06T12:00:01Z" }),
    };

    const [updated] = applyBacktestJobUpdate([running], {
      job: job({
        status: "failed",
        failure_code: "market_data_unavailable",
        failure_detail: "market_data_issue",
        retryable: true,
        finished_at: "2026-06-06T12:00:04Z",
      }),
      run: null,
    });

    expect(updated.kind).toBe("backtest_job");
    expect(updated.backtestJob?.status).toBe("failed");
    expect(pendingBacktestJobIds([updated])).toEqual([]);
  });

  test("succeeded durable job with a run hydrates into a result card", () => {
    const [updated] = applyBacktestJobUpdate([queuedJobMessage()], {
      job: job({
        status: "succeeded",
        result_run_id: "run-1",
        finished_at: "2026-06-06T12:00:04Z",
      }),
      run: run(),
    });

    expect(updated.kind).toBe("strategy_result");
    expect(updated.result?.runId).toBe("run-1");
    expect(updated.result?.strategyName).toBe("AAPL buy and hold");
    expect(updated.result?.actions?.[0].payload?.run_id).toBe("run-1");
  });

  test("succeeded durable job replaces queued placeholder with completed readout", () => {
    const resultReadout =
      "**Quick take**\n\nBackend generated readout.\n\n- Tested: AAPL buy and hold.";
    const [updated] = applyBacktestJobUpdate([queuedJobMessage()], {
      job: job({
        status: "succeeded",
        result_run_id: "run-1",
        finished_at: "2026-06-06T12:00:04Z",
      }),
      run: run(),
      result_readout: resultReadout,
    });

    expect(updated.kind).toBe("strategy_result");
    expect(updated.content).toBe(resultReadout);
    expect(updated.content).not.toContain("I started the backtest");
    expect(updated.content).not.toContain("as soon as it is ready");
  });

  test("durable job hydration does not generate backend-owned quick takes in the frontend", () => {
    const source = readFileSync(join(root, "lib/chat-backtest-jobs.ts"), "utf-8");

    expect(source).not.toContain("completedResultReadout");
    expect(source).not.toContain("heroDeltaEvidenceView");
    expect(source).not.toContain("defaultResultCardDisplayCopy");
  });

  test("succeeded durable job settles its confirmation as run complete", () => {
    const confirmationMessage: Message = supersedePriorConfirmations(
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "active",
          title: "AAPL buy and hold",
          statusLabel: "Ready to run",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
        actions: [],
      },
      "Running",
    );
    const queuedMessages = normalizeConfirmationHistory(
      applyBacktestJobUpdate([confirmationMessage, queuedJobMessage()], {
        job: job({ status: "queued" }),
        run: null,
      }),
    );
    const completedMessages = normalizeConfirmationHistory(
      applyBacktestJobUpdate(queuedMessages, {
        job: job({
          status: "succeeded",
          result_run_id: "run-1",
          finished_at: "2026-06-06T12:00:04Z",
        }),
        run: run(),
      }),
    );

    expect(completedMessages[0].confirmation?.statusLabel).toBe("Run complete");
    expect(completedMessages[0].confirmation?.status).toBe("run_complete");
    expect(completedMessages[1].kind).toBe("strategy_result");
  });

  test("queued durable job clears stale running confirmation status", () => {
    const confirmationMessage: Message = supersedePriorConfirmations(
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "active",
          title: "AAPL buy and hold",
          statusLabel: "Ready to run",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
        actions: [],
      },
      "Running",
    );

    const [settledConfirmation, activeJob] = applyBacktestJobUpdate(
      [confirmationMessage, queuedJobMessage()],
      {
        job: job({ status: "queued" }),
        run: null,
      },
    );

    expect(settledConfirmation.confirmation?.statusLabel).toBe("Request sent");
    expect(settledConfirmation.confirmation?.status).toBe("request_sent");
    expect(activeJob.kind).toBe("backtest_job");
    expect(activeJob.backtestJob?.status).toBe("queued");
  });

  test("failed durable job settles request-sent confirmation status", () => {
    const confirmationMessage: Message = supersedePriorConfirmations(
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "active",
          title: "AAPL buy and hold",
          statusLabel: "Ready to run",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
        actions: [],
      },
      "Running",
    );
    const queuedMessages = applyBacktestJobUpdate(
      [confirmationMessage, queuedJobMessage()],
      {
        job: job({ status: "queued" }),
        run: null,
      },
    );
    const [settledConfirmation, failedJob] = applyBacktestJobUpdate(
      queuedMessages,
      {
        job: job({
          status: "failed",
          failure_code: "market_data_unavailable",
          failure_detail: "market_data_issue",
          retryable: true,
          finished_at: "2026-06-06T12:00:04Z",
        }),
        run: null,
      },
    );

    expect(settledConfirmation.confirmation?.statusLabel).toBe("Could not run");
    expect(settledConfirmation.confirmation?.status).toBe("could_not_run");
    expect(failedJob.kind).toBe("backtest_job");
    expect(failedJob.backtestJob?.status).toBe("failed");
  });

  test("expired durable job settles request-sent confirmation status", () => {
    const confirmationMessage: Message = supersedePriorConfirmations(
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "active",
          title: "AAPL buy and hold",
          statusLabel: "Ready to run",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
        actions: [],
      },
      "Running",
    );
    const queuedMessages = applyBacktestJobUpdate(
      [confirmationMessage, queuedJobMessage()],
      {
        job: job({ status: "running" }),
        run: null,
      },
    );
    const [settledConfirmation, expiredJob] = applyBacktestJobUpdate(
      queuedMessages,
      {
        job: job({
          status: "expired",
          finished_at: "2026-06-06T12:00:04Z",
        }),
        run: null,
      },
    );

    expect(settledConfirmation.confirmation?.statusLabel).toBe("Not completed");
    expect(settledConfirmation.confirmation?.status).toBe("not_completed");
    expect(expiredJob.kind).toBe("backtest_job");
    expect(expiredJob.backtestJob?.status).toBe("expired");
  });

  test("canceled durable job settles request-sent confirmation status", () => {
    const confirmationMessage: Message = supersedePriorConfirmations(
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "active",
          title: "AAPL buy and hold",
          statusLabel: "Ready to run",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
        actions: [],
      },
      "Running",
    );
    const queuedMessages = applyBacktestJobUpdate(
      [confirmationMessage, queuedJobMessage()],
      {
        job: job({ status: "running" }),
        run: null,
      },
    );
    const [settledConfirmation, canceledJob] = applyBacktestJobUpdate(
      queuedMessages,
      {
        job: job({
          status: "canceled",
          finished_at: "2026-06-06T12:00:04Z",
        }),
        run: null,
      },
    );

    expect(settledConfirmation.confirmation?.statusLabel).toBe("Not completed");
    expect(settledConfirmation.confirmation?.status).toBe("not_completed");
    expect(canceledJob.kind).toBe("backtest_job");
    expect(canceledJob.backtestJob?.status).toBe("canceled");
    expect(pendingBacktestJobIds([canceledJob])).toEqual([]);
  });

  test("job card locale copy does not expose implementation plumbing", () => {
    const localeFiles = [
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    ];
    const forbidden = [
      /workflow/i,
      /chat stream/i,
      /durable job/i,
      /job record/i,
      /canonical run/i,
      /flujo/i,
      /stream/i,
      /trabajo durable/i,
      /ejecuci[oó]n can[oó]nica/i,
    ];

    for (const copy of localeFiles) {
      const parsed = JSON.parse(copy) as { chat?: { backtest_job?: unknown } };
      const jobCopy = JSON.stringify(parsed.chat?.backtest_job ?? {});
      for (const pattern of forbidden) {
        expect(jobCopy).not.toMatch(pattern);
      }
    }
  });

  test("chat stream, polling, and reload paths use durable job helpers", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain("getBacktestJob");
    expect(chat).toContain("backtestJobMessageFromApi(m)");
    expect(chat).toContain("const finalBacktestJob = backtestJobFromFinalPayload(finalPayload)");
    expect(chat).toContain('kind: "backtest_job"');
    expect(chat).toContain("applyBacktestJobUpdate(");
    expect(chat).toContain("pendingBacktestJobKey");
    expect(chat).toContain("response.job.status === \"succeeded\" && !response.run");
    expect(chat).toContain("response.job.status === \"running\"");
    expect(chat).not.toContain('workflow_proof');
  });
});
