import { describe, expect, test } from "bun:test";
import {
  BrowserSafetyMonitor,
  CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES,
  browserSafetyDetail,
  confirmationContinuityChecks,
  distinctConfirmationFacts,
  latestConfirmationFacts,
  type ConfirmationFacts,
  type PersistedMessageItem,
} from "../e2e/support/guest-qa";

const requestedRange = { start: "2025-07-25", end: "2026-07-25" };
const effectiveRange = { start: "2025-07-25", end: "2026-07-24" };

function confirmationMessage(
  messageId: string,
  confirmationId: string,
  symbol: string,
  overrides: {
    benchmark?: string | null;
    requested?: Record<string, string>;
    effective?: Record<string, string>;
  } = {},
): PersistedMessageItem {
  const launchPayload: Record<string, unknown> = {
    requested_date_range: overrides.requested ?? requestedRange,
  };
  if (overrides.benchmark !== null) {
    launchPayload.benchmark_symbol = overrides.benchmark ?? "SPY";
  }
  return {
    id: messageId,
    conversation_id: "conversation-fixture",
    role: "assistant",
    content: "redacted fixture prose",
    metadata: {
      confirmation_payload: {
        strategy: {
          asset_universe: [symbol],
          date_range: overrides.effective ?? effectiveRange,
        },
        launch_payload: launchPayload,
      },
      confirmation_card: {
        confirmation_id: confirmationId,
        assumptions: ["Benchmark: SPY"],
      },
    },
  };
}

const initial = confirmationMessage(
  "message-initial",
  "confirmation-initial",
  "AAPL",
);
const refined = confirmationMessage(
  "message-refined",
  "confirmation-refined",
  "MSFT",
);

describe("guest Check 4 confirmation selection", () => {
  test("rejects a stale confirmation while waiting for a distinct artifact", () => {
    const initialFacts = latestConfirmationFacts([initial]);

    expect(distinctConfirmationFacts([initial], initialFacts)).toBeNull();
  });

  test("rejects a candidate when either identity is reused", () => {
    const initialFacts = latestConfirmationFacts([initial]);
    const reusedMessageId = confirmationMessage(
      "message-initial",
      "confirmation-refined",
      "MSFT",
    );
    const reusedConfirmationId = confirmationMessage(
      "message-refined",
      "confirmation-initial",
      "MSFT",
    );

    expect(
      distinctConfirmationFacts([initial, reusedMessageId], initialFacts),
    ).toBeNull();
    expect(
      distinctConfirmationFacts([initial, reusedConfirmationId], initialFacts),
    ).toBeNull();
  });

  test("selects the newest confirmation with distinct message and confirmation ids", () => {
    const initialFacts = latestConfirmationFacts([initial]);
    const newest = confirmationMessage(
      "message-newest",
      "confirmation-newest",
      "MSFT",
    );

    expect(
      distinctConfirmationFacts([initial, refined, newest], initialFacts),
    ).toMatchObject({
      messageId: "message-newest",
      confirmationId: "confirmation-newest",
      assetUniverse: ["MSFT"],
      benchmark: "SPY",
      requestedDateRange: requestedRange,
      effectiveDateRange: effectiveRange,
    });
  });

  test("requires a typed benchmark instead of searching card JSON", () => {
    const misleadingCard = confirmationMessage(
      "message-missing-benchmark",
      "confirmation-missing-benchmark",
      "MSFT",
      { benchmark: null },
    );

    expect(() => latestConfirmationFacts([misleadingCard])).toThrow(
      "typed benchmark",
    );
  });
});

describe("guest Check 4 continuity assertions", () => {
  const exactUpdate = "Use MSFT instead of AAPL.";
  const updateMessage: PersistedMessageItem = {
    id: "message-user-update",
    conversation_id: "conversation-fixture",
    role: "user",
    content: exactUpdate,
  };
  const initialFacts = latestConfirmationFacts([initial]);
  const refinedFacts = latestConfirmationFacts([refined]);
  const expectedPassing = {
    updateMessagePersisted: true,
    assetUniverseExactlyMsft: true,
    benchmarkExactlySpy: true,
    requestedDateRangeUnchanged: true,
    effectiveDateRangeUnchanged: true,
  };

  test.each([
    {
      name: "exact update-message persistence",
      key: "updateMessagePersisted" as const,
      messages: [],
      facts: refinedFacts,
    },
    {
      name: "asset universe",
      key: "assetUniverseExactlyMsft" as const,
      messages: [updateMessage],
      facts: { ...refinedFacts, assetUniverse: ["AAPL"] },
    },
    {
      name: "benchmark",
      key: "benchmarkExactlySpy" as const,
      messages: [updateMessage],
      facts: { ...refinedFacts, benchmark: "QQQ" },
    },
    {
      name: "requested date range",
      key: "requestedDateRangeUnchanged" as const,
      messages: [updateMessage],
      facts: {
        ...refinedFacts,
        requestedDateRange: { ...requestedRange, start: "2025-08-01" },
      },
    },
    {
      name: "effective date range",
      key: "effectiveDateRangeUnchanged" as const,
      messages: [updateMessage],
      facts: {
        ...refinedFacts,
        effectiveDateRange: { ...effectiveRange, end: "2026-07-23" },
      },
    },
  ])("$name fails independently with a useful assertion", ({ key, messages, facts }) => {
    const checks = confirmationContinuityChecks(
      initialFacts,
      facts as ConfirmationFacts,
      messages,
      exactUpdate,
    );

    expect(checks).toEqual({ ...expectedPassing, [key]: false });
    expect(CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES[key].length).toBeGreaterThan(
      20,
    );
  });
});

describe("browser safety evidence", () => {
  test("records only sanitized endpoint, category, check, and phase detail", () => {
    const detail = browserSafetyDetail({
      event: "failed_request",
      rawUrl:
        "http://127.0.0.1:8000/api/v1/conversations/4f8c3dea-c926-4e33-9d50-959bd43d4868/messages?email=founder@example.com&token=secret",
      method: "POST",
      rawError:
        "net::ERR_CONNECTION_REFUSED bearer secret founder@example.com",
      status: null,
      context: { check: 4, phase: "teardown" },
    });
    const serialized = JSON.stringify(detail);

    expect(detail).toEqual({
      event: "failed_request",
      component: "network",
      endpoint: "POST /api/v1/conversations/:id/messages",
      status: null,
      category: "connection_refused",
      check: 4,
      phase: "teardown",
    });
    expect(serialized).not.toContain("founder@example.com");
    expect(serialized).not.toContain("secret");
    expect(serialized).not.toContain("token");
    expect(serialized).not.toContain("bearer");
    expect(serialized).not.toContain("4f8c3dea");

    expect(
      browserSafetyDetail({
        event: "console_error",
        rawError:
          "Hydration failed with bearer secret founder@example.com",
        context: { check: 2, phase: "product" },
      }),
    ).toEqual({
      event: "console_error",
      component: "browser_console",
      endpoint: null,
      status: null,
      category: "hydration_error",
      check: 2,
      phase: "product",
    });
  });

  test("the attached monitor records the live product-to-teardown phase change", () => {
    type StubHandler = (payload: unknown) => void;
    const handlers = new Map<string, StubHandler[]>();
    const pageStub = {
      on(event: string, handler: StubHandler) {
        handlers.set(event, [...(handlers.get(event) ?? []), handler]);
        return pageStub;
      },
      emit(event: string, payload: unknown) {
        for (const handler of handlers.get(event) ?? []) handler(payload);
      },
    };
    let phase = "product" as "product" | "teardown";
    const monitor = new BrowserSafetyMonitor(() => ({ check: 4, phase }));
    monitor.attach(
      pageStub as unknown as Parameters<BrowserSafetyMonitor["attach"]>[0],
    );

    pageStub.emit("console", {
      type: () => "error",
      text: () => "Hydration failed with founder@example.com",
    });
    phase = "teardown";
    pageStub.emit("requestfailed", {
      url: () =>
        "http://127.0.0.1:8000/api/v1/conversations/4f8c3dea-c926-4e33-9d50-959bd43d4868/messages?token=secret",
      method: () => "POST",
      failure: () => ({ errorText: "net::ERR_ABORTED bearer secret" }),
    });

    expect(monitor.detailSnapshot()).toEqual([
      {
        event: "console_error",
        component: "browser_console",
        endpoint: null,
        status: null,
        category: "hydration_error",
        check: 4,
        phase: "product",
      },
      {
        event: "failed_request",
        component: "network",
        endpoint: "POST /api/v1/conversations/:id/messages",
        status: null,
        category: "aborted",
        check: 4,
        phase: "teardown",
      },
    ]);
    expect(JSON.stringify(monitor.detailSnapshot())).not.toMatch(
      /founder|secret|bearer|token|4f8c3dea/i,
    );
  });
});
