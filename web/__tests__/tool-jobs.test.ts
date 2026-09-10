import { describe, expect, test } from "bun:test";

import type { Message, ToolJob } from "../components/chat/types";
import type { ApiMessage, BacktestJob, BacktestJobResponse } from "../lib/argus-api";
import {
  applyBacktestJobUpdate,
  pendingBacktestJobIds,
} from "../lib/chat-backtest-jobs";
import {
  applyResearchJobAnswer,
  hydrateMessagesFromApi,
} from "../components/chat/chat-message-projection";
import type { ToolResultCard } from "../lib/tool-result-card";
import { toolCardFixture } from "./fixtures/tool-result-card";

const conversationId = crypto.randomUUID();
const requestMessageId = crypto.randomUUID();

function toolJob(overrides: Partial<BacktestJob> = {}): ToolJob {
  return {
    call_id: crypto.randomUUID(),
    tool_name: "thorough_research",
    artifact_id: crypto.randomUUID(),
    job: {
      id: crypto.randomUUID(),
      conversation_id: conversationId,
      request_message_id: requestMessageId,
      operation_scope: "chat.research",
      status: "queued",
      retryable: false,
      ...overrides,
    },
  };
}

function toolMessage(toolJobs: ToolJob[]): Message {
  return {
    id: crypto.randomUUID(),
    role: "ai",
    kind: "text",
    content: "",
    toolJobs,
  };
}

function toolCard(call: ToolJob, value: number): ToolResultCard {
  const fixture = toolCardFixture({
    call_id: call.call_id, tool_name: call.tool_name, artifact_id: call.artifact_id,
  });
  return {
    ...fixture,
    outcome: { ...fixture.outcome, result: { value } },
    presentation: {
      ...fixture.presentation,
      answer: { ...fixture.presentation.answer!, value },
    },
  };
}

function completedResponse(call: ToolJob, value: number): BacktestJobResponse {
  const answer: ApiMessage = {
    id: crypto.randomUUID(), conversation_id: conversationId, role: "assistant",
    content: `Result ${value}`, created_at: new Date().toISOString(),
    metadata: { tool_result_cards: [toolCard(call, value)] },
  };
  return { job: { ...call.job, status: "succeeded" }, run: null, result_message: answer };
}

function applyResponse(messages: Message[], response: BacktestJobResponse): Message[] {
  return applyResearchJobAnswer(applyBacktestJobUpdate(messages, response), response);
}

describe("shared plural tool jobs", () => {
  test("two calls to the same tool remain independently pollable", () => {
    const calls = [toolJob(), toolJob({ status: "running" })];
    const message = toolMessage(calls);

    expect(pendingBacktestJobIds([message])).toEqual(
      calls.map((call) => call.job.id),
    );
  });

  test("a response updates only its own call and preserves its sibling", () => {
    const calls = [toolJob(), toolJob()];
    const message = toolMessage(calls);
    const response: BacktestJobResponse = {
      job: { ...calls[1]!.job, status: "running" },
      run: null,
    };

    const [updated] = applyBacktestJobUpdate([message], response);

    expect(updated?.toolJobs?.[0]).toBe(calls[0]);
    expect(updated?.toolJobs?.[1]).toEqual({
      ...calls[1],
      job: response.job,
    });
    expect(updated?.id).toBe(message.id);
  });

  test("live and nested durable metadata retain every valid call identity", async () => {
    const jobs = await import("../lib/chat-backtest-jobs");
    const calls = [toolJob(), toolJob()];
    const invalidCall = { ...toolJob(), tool_name: " " };
    const wire = [calls[0], invalidCall, calls[1], calls[0]];

    expect(typeof jobs.toolJobsFromMetadata).toBe("function");
    const live = jobs.toolJobsFromMetadata({ tool_jobs: wire });
    const hydrated = jobs.toolJobsFromMetadata({
      final_response_payload: { tool_jobs: wire },
    });

    expect(live).toEqual(hydrated);
    expect(live.map((call) => call.call_id)).toEqual(
      calls.map((call) => call.call_id),
    );
    expect(live.map((call) => call.job.id)).toEqual(
      calls.map((call) => call.job.id),
    );
  });

  test("durable result identity survives parsing without rearming settled calls", async () => {
    const { toolJobsFromMetadata } = await import("../lib/chat-backtest-jobs");
    const settled = toolJob({ status: "succeeded" });
    const resultMessageId = crypto.randomUUID();
    const [parsed] = toolJobsFromMetadata({
      tool_jobs: [{ ...settled, result_message_id: resultMessageId }],
    });

    expect(parsed?.resultMessageId).toBe(resultMessageId);
    expect(pendingBacktestJobIds([toolMessage([parsed!])])).toEqual([]);
  });

  for (const status of ["queued", "running", "succeeded"] as const) {
    test(`${status} calls keep polling until durable output is available`, () => {
      const call = toolJob({ status });
      const calls = [call, { ...toolJob({ status }), resultMessageId: crypto.randomUUID() }];

      expect(pendingBacktestJobIds([toolMessage(calls)])).toEqual(
        (status === "succeeded" ? [call] : calls).map((entry) => entry.job.id),
      );
    });
  }

  test("legacy and plural job owners share one deduplicated polling set", () => {
    const calls = [toolJob(), toolJob()];
    const legacy: Message = {
      id: crypto.randomUUID(), role: "ai", kind: "backtest_job",
      backtestJob: calls[0]!.job,
    };

    expect(pendingBacktestJobIds([legacy, toolMessage(calls)])).toEqual(
      calls.map((call) => call.job.id),
    );
  });

  test("out-of-order completions retain both results and settle only their own call", () => {
    const calls = [toolJob(), toolJob()];
    const source = { ...toolMessage(calls), toolResultCards: calls.map(toolCard) };
    const later: Message = { id: crypto.randomUUID(), role: "user", content: "Thanks" };
    const responses = calls.map(completedResponse);

    const first = applyResponse([source, later], responses[1]!);
    expect(pendingBacktestJobIds(first)).toEqual([calls[0]!.job.id]);
    expect(first[0]?.toolResultCards?.map((card) => card.call_id)).toEqual([calls[0]!.call_id]);
    expect(first[0]?.toolJobs?.map((call) => call.resultMessageId)).toEqual([
      undefined, responses[1]!.result_message!.id,
    ]);

    const completed = applyResponse(first, responses[0]!);
    expect(pendingBacktestJobIds(completed)).toEqual([]);
    expect(completed[0]?.toolResultCards).toEqual([]);
    expect(completed.flatMap((message) => message.toolResultCards ?? []))
      .toEqual([toolCard(calls[1]!, 1), toolCard(calls[0]!, 0)]);
    expect(completed.at(-1)?.id).toBe(later.id);
    expect(applyResponse(completed, responses[1]!)).toEqual(completed);
  });

  test("reload keeps separate answers and retires only their matching placeholders", () => {
    const calls = [toolJob(), toolJob()];
    const responses = calls.map(completedResponse);
    const source: ApiMessage = {
      id: crypto.randomUUID(), conversation_id: conversationId, role: "assistant",
      content: "", created_at: new Date().toISOString(),
      metadata: { tool_jobs: calls, tool_result_cards: calls.map(toolCard) },
    };
    const hydrated = hydrateMessagesFromApi([
      source, responses[1]!.result_message!, responses[0]!.result_message!,
    ]).messages;

    expect(hydrated[0]?.toolResultCards).toEqual([]);
    expect(hydrated[0]?.toolJobs?.map((call) => call.resultMessageId)).toEqual(
      responses.map((response) => response.result_message!.id),
    );
    expect(hydrated.flatMap((message) => message.toolResultCards ?? []))
      .toEqual([toolCard(calls[1]!, 1), toolCard(calls[0]!, 0)]);

    // Persisted queued jobs still need current durable status. The answers
    // already in the transcript must not duplicate when those polls finish.
    const reconciled = responses.reduce(applyResponse, hydrated);
    expect(pendingBacktestJobIds(reconciled)).toEqual([]);
    expect(reconciled).toHaveLength(hydrated.length);
  });

  test("a failed call keeps its typed failure while its sibling continues", () => {
    const calls = [toolJob(), toolJob()];
    const response = completedResponse(calls[0]!, 0);
    const failure = toolCard(calls[0]!, 0);
    failure.outcome = {
      status: "unavailable", result: null,
      failure: { code: "research_unavailable", fields: [] },
    };
    failure.presentation.answer = null;
    response.job.status = "failed";
    response.result_message!.metadata = { tool_result_cards: [failure] };
    const source = { ...toolMessage(calls), toolResultCards: calls.map(toolCard) };

    const updated = applyResponse([source], response);

    expect(pendingBacktestJobIds(updated)).toEqual([calls[1]!.job.id]);
    const result = updated[1]?.toolResultCards?.[0];
    expect(result?.call_id).toBe(calls[0]!.call_id);
    expect(result?.outcome.status).toBe("unavailable");
    expect(result?.presentation.answer).toBeNull();
    expect(updated[0]?.toolJobs?.[1]).toBe(calls[1]);
  });
});
