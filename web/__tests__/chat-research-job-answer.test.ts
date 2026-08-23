import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Message } from "../components/chat/types";
import type { ApiMessage, BacktestJob } from "../lib/argus-api";
import {
  applyBacktestJobUpdate,
  backtestJobMessageFromApi,
  pendingBacktestJobIds,
} from "../lib/chat-backtest-jobs";

// Loaded lazily so the pending-set test below fails on behavior, not on a
// missing export, against a tree that predates the in-place projection.
async function projection() {
  const [
    { applyResearchJobAnswer },
    { backtestJobResponseAwaitsPolling, backtestJobCardAwaitsPolling },
  ] = await Promise.all([
    import("../components/chat/chat-message-projection"),
    import("../lib/chat-backtest-jobs"),
  ]);
  return { applyResearchJobAnswer, backtestJobResponseAwaitsPolling, backtestJobCardAwaitsPolling };
}

const root = join(import.meta.dir, "..");

// Production 2026-08-21 (conversation cb7b326d): a thorough research job
// succeeded, the card flipped to "Research ready. The full answer is below."
// and nothing painted below it until a reload. The answer is a new assistant
// message, so the poll response carries it the way a backtest's carries
// `run`, and the view inserts it after the card: no transcript reload (so
// nothing can blank) and no dependence on the conversation lock.

function job(overrides: Partial<BacktestJob> = {}): BacktestJob {
  return {
    id: "job-1",
    conversation_id: "conversation-1",
    request_message_id: "request-message-1",
    confirmation_message_id: null,
    status: "queued",
    operation_scope: "chat.research",
    result_run_id: null,
    failure_code: null,
    failure_detail: null,
    retryable: false,
    queued_at: "2026-08-22T01:25:21Z",
    started_at: null,
    finished_at: null,
    created_at: "2026-08-22T01:25:21Z",
    updated_at: "2026-08-22T01:25:21Z",
    ...overrides,
  };
}

function card(currentJob: BacktestJob = job()): Message {
  const message = backtestJobMessageFromApi({
    id: "assistant-job-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "Researching this one thoroughly.",
    created_at: "2026-08-22T01:25:21Z",
    metadata: { backtest_job: currentJob },
  });
  if (!message) throw new Error("Expected a hydrated job card.");
  return message;
}

function answer(): ApiMessage {
  return {
    id: "answer-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "# HOOD vs. JPM vs. SCHW\n\nThree very different animals.",
    created_at: "2026-08-22T01:25:58Z",
    metadata: {
      conversation_mode: "guide",
      research: {
        sources: [
          { title: "JPM 10-K", domain: "example.test", url: "https://example.test/jpm" },
        ],
      },
      next_experiments: {
        version: "argus_next_experiments/v1",
        rows: [
          {
            kind: "prebaked",
            label: "Test HOOD vs JPM and SCHW",
            label_key: "prebaked_comparison",
            send_text: "Test HOOD against JPM and SCHW over 3 years",
          },
        ],
      },
    },
  };
}

describe("research job answer", () => {
  test("the answer rides the job response and paints in place after its card", async () => {
    const { applyResearchJobAnswer } = await projection();
    const succeeded = job({ status: "succeeded", finished_at: "2026-08-22T01:25:58Z" });
    const response = { job: succeeded, run: null, result_message: answer() };
    const later: Message = { id: "later-user", role: "user", kind: "text", content: "thanks" };

    const painted = applyResearchJobAnswer(
      applyBacktestJobUpdate([card(), later], response),
      response,
    );

    expect(painted.map((message) => message.id)).toEqual([
      "assistant-job-1",
      "answer-1",
      "later-user",
    ]);
    expect(painted[0]?.kind).toBe("backtest_job");
    expect(painted[0]?.backtestJob?.status).toBe("succeeded");
    expect(painted[1]?.kind).toBe("text");
    expect(painted[1]?.content).toContain("HOOD vs. JPM vs. SCHW");
    expect(painted[1]?.researchSources?.[0]?.url).toBe("https://example.test/jpm");
    expect(painted[1]?.nextExperiments?.[0]?.sendText).toBe(
      "Test HOOD against JPM and SCHW over 3 years",
    );
  });

  test("re-polling a settled job never duplicates the answer", async () => {
    const { applyResearchJobAnswer } = await projection();
    // A reload re-arms the hydrated card at its persisted "queued" status and
    // polls again; the answer is already in the transcript by then.
    const response = { job: job({ status: "succeeded" }), run: null, result_message: answer() };
    const painted = applyResearchJobAnswer([card()], response);

    expect(painted).toHaveLength(2);
    expect(applyResearchJobAnswer(painted, response)).toBe(painted);
  });

  test("a terminal research job's message paints for a failure too, and only research responses insert", async () => {
    const { applyResearchJobAnswer } = await projection();
    const note: ApiMessage = {
      ...answer(),
      id: "note-1",
      content: "I couldn't finish that thorough research run.",
      metadata: { conversation_mode: "guide" },
    };
    const failed = { job: job({ status: "failed" }), run: null, result_message: note };
    const painted = applyResearchJobAnswer([card(job({ status: "failed" }))], failed);
    expect(painted.map((message) => message.id)).toEqual(["assistant-job-1", "note-1"]);
    expect(painted[1]?.content).toContain("couldn't finish");
    expect(painted[0]?.researchResultMessageId).toBe("note-1");

    const backtest = {
      job: job({ status: "succeeded", operation_scope: "chat.run_backtest" }),
      run: null,
      result_message: answer(),
    };
    const withoutAnswer = { job: job({ status: "succeeded" }), run: null, result_message: null };
    expect(applyResearchJobAnswer([card()], backtest)).toHaveLength(1);
    expect(applyResearchJobAnswer([card()], withoutAnswer)).toHaveLength(1);
  });

  test("one null result_message never ends the story: the poll continues and the card stays pending", async () => {
    // Review of #532: a succeeded research job was terminal for polling, so a
    // single response without the message (replica lag, a read that returned
    // nothing) painted nothing and nothing re-armed, the original symptom
    // through a new door. Now the response keeps polling (bounded by the
    // poller's attempt cap) and the card stays in the pending set until its
    // message is in the view, so reopening the conversation polls again.
    const { backtestJobResponseAwaitsPolling, backtestJobCardAwaitsPolling, applyResearchJobAnswer } =
      await projection();
    const succeeded = job({ status: "succeeded" });

    expect(backtestJobResponseAwaitsPolling({ job: succeeded, run: null, result_message: null })).toBe(true);
    expect(backtestJobResponseAwaitsPolling({ job: succeeded, run: null, result_message: answer() })).toBe(false);
    expect(backtestJobResponseAwaitsPolling({ job: job({ status: "running" }), run: null, result_message: null })).toBe(true);
    expect(backtestJobResponseAwaitsPolling({ job: job({ status: "failed" }), run: null, result_message: null })).toBe(false);
    const backtestJob = job({ status: "succeeded", operation_scope: "chat.run_backtest" });
    expect(backtestJobResponseAwaitsPolling({ job: backtestJob, run: null, result_message: null })).toBe(true);

    const unsettled = card(succeeded);
    expect(backtestJobCardAwaitsPolling(unsettled)).toBe(true);
    expect(pendingBacktestJobIds([unsettled])).toEqual(["job-1"]);
    const painted = applyResearchJobAnswer([unsettled], { job: succeeded, run: null, result_message: answer() });
    expect(painted[0]?.researchResultMessageId).toBe("answer-1");
    expect(backtestJobCardAwaitsPolling(painted[0]!)).toBe(false);
    expect(pendingBacktestJobIds(painted)).toEqual([]);
    // A backtest card keeps polling until it becomes a result card.
    expect(pendingBacktestJobIds([{ ...card(backtestJob), id: "assistant-job-2" }])).toEqual(["job-1"]);
  });

  test("the poller projects the answer and the completion handler never reloads", () => {
    const reconciliation = readFileSync(join(root, "lib/chat-run-reconciliation.ts"), "utf-8");
    const applyStart = reconciliation.indexOf("const applyResponse = useCallback(");
    const applyResponse = reconciliation.slice(
      applyStart,
      reconciliation.indexOf("useEffect(() => {", applyStart),
    );
    expect(applyResponse).toContain("applyResearchJobAnswer(");
    expect(applyResponse).toContain("applyBacktestJobUpdate(current, response)");
    expect(reconciliation).toContain("backtestJobResponseAwaitsPolling(response)");

    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const handler = chat.slice(
      chat.indexOf("const handleDurableJobCompletion"),
      chat.indexOf("useBacktestJobPolling(messages"),
    );
    expect(handler).toContain(
      'invalidateTranscriptForMutation(targetConversationId, "durable_job_completion")',
    );
    expect(handler).toContain("promoteCanonicalConversationActivityTranscript");
    expect(handler).not.toContain("chat.research");
    expect(handler).not.toContain("navigateConversationTranscript");
    expect(handler).not.toContain("isConversationLocked");
    expect(chat).not.toContain("reloadActiveTranscriptRef");
  });
});
