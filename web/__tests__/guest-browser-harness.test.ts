import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  BrowserSafetyMonitor,
  CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES,
  assertSafeEvidence,
  binaryEvidenceDiffers,
  browserSafetyDetail,
  confirmationContinuityChecks,
  distinctConfirmationFacts,
  emptyEvidence,
  expectedMutationDeltasOnly,
  latestConfirmationFacts,
  latestResultFacts,
  productFailedRequestsForCheck,
  resultTruthStayedStable,
  strictUtcTimestampsEqual,
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

describe("guest QA strict UTC timestamp comparison", () => {
  test("treats API and Postgres UTC encodings of the same microsecond as equal", () => {
    expect(
      strictUtcTimestampsEqual(
        "2026-08-01T08:03:09.708198Z",
        "2026-08-01 08:03:09.708198+00",
      ),
    ).toBe(true);
  });

  test("rejects a real one-microsecond difference", () => {
    expect(
      strictUtcTimestampsEqual(
        "2026-08-01T08:03:09.708198Z",
        "2026-08-01 08:03:09.708199+00",
      ),
    ).toBe(false);
  });

  test("fails closed for invalid timestamps and non-UTC offsets", () => {
    expect(
      strictUtcTimestampsEqual(
        "not-a-timestamp",
        "2026-08-01T08:03:09.708198Z",
      ),
    ).toBe(false);
    expect(
      strictUtcTimestampsEqual(
        "2026-08-01T09:03:09.708198+01:00",
        "2026-08-01T08:03:09.708198Z",
      ),
    ).toBe(false);
  });
});

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
  test("allows only the expected sanitized analytics write at a conversion gate", () => {
    const before = {
      "POST /api/v1/analytics/guest-events": 2,
      "POST /api/v1/chat/stream": 4,
    };

    expect(
      expectedMutationDeltasOnly(before, {
        ...before,
        "POST /api/v1/analytics/guest-events": 3,
      }, {
        "POST /api/v1/analytics/guest-events": 1,
      }),
    ).toBe(true);
    expect(
      expectedMutationDeltasOnly(before, {
        ...before,
        "POST /api/v1/analytics/guest-events": 3,
        "POST /api/v1/chat/stream": 5,
      }, {
        "POST /api/v1/analytics/guest-events": 1,
      }),
    ).toBe(false);
  });

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
    pageStub.emit("response", {
      status: () => 429,
      url: () =>
        "http://127.0.0.1:8000/api/v1/backtests/4f8c3dea-c926-4e33-9d50-959bd43d4868?token=secret",
      request: () => ({ method: () => "POST" }),
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
        endpoint: "POST /api/v1/backtests/:id",
        status: 429,
        category: "http_client_error",
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

  test("selects a product-phase failed request without accepting teardown noise", () => {
    const expected = browserSafetyDetail({
      event: "failed_request",
      rawUrl: "http://127.0.0.1:8000/api/v1/chat/stream",
      method: "POST",
      rawError: "net::ERR_CONNECTION_RESET",
      context: { check: 18, phase: "product" },
    });
    const unrelated = browserSafetyDetail({
      event: "failed_request",
      rawUrl: "http://127.0.0.1:8000/api/v1/me",
      method: "GET",
      rawError: "net::ERR_ABORTED",
      context: { check: 18, phase: "teardown" },
    });

    expect(productFailedRequestsForCheck([expected, unrelated], 18)).toEqual([
      {
        event: "failed_request",
        component: "network",
        endpoint: "POST /api/v1/chat/stream",
        status: null,
        category: "connection_reset",
        check: 18,
        phase: "product",
      },
    ]);
  });

  test("detects credential-shaped data on a non-loopback request without retaining it", () => {
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
    const monitor = new BrowserSafetyMonitor();
    monitor.attach(
      pageStub as unknown as Parameters<BrowserSafetyMonitor["attach"]>[0],
    );

    pageStub.emit("request", {
      url: () => "https://example.invalid/collect?token=opaque-secret",
      method: () => "POST",
      headers: () => ({ authorization: "Bearer opaque-secret" }),
      postData: () => '{"cookie":"opaque-secret"}',
    });

    expect(monitor.hostedWrites).toBe(1);
    expect(monitor.credentialExposure).toBe(1);
    expect(JSON.stringify(monitor.detailSnapshot())).not.toContain(
      "opaque-secret",
    );
  });

  test("accepts only hashed identifiers and classified endpoint evidence", () => {
    const previousCandidate = process.env.ARGUS_CANDIDATE_SHA;
    process.env.ARGUS_CANDIDATE_SHA = "a".repeat(40);
    try {
      const safe = emptyEvidence();
      safe.owner_labels = ["b".repeat(20)];
      safe.normalized_mutation_counts = {
        "POST /api/v1/auth/guest/link": 1,
      };
      assertSafeEvidence(safe);

      const unsafeCategory = {
        ...safe,
        browser_safety_details: [
          {
            event: "console_error" as const,
            component: "browser_console" as const,
            endpoint: null,
            status: null,
            category: "raw transcript prose",
            check: 2 as const,
            phase: "product" as const,
          },
        ],
      };
      expect(() => assertSafeEvidence(unsafeCategory)).toThrow(
        "unsafe browser safety detail",
      );

      const unsafeEndpoint = {
        ...safe,
        normalized_mutation_counts: {
          "POST /api/v1/feedback?token=opaque": 1,
        },
      };
      expect(() => assertSafeEvidence(unsafeEndpoint)).toThrow(
        "unsafe mutation endpoint",
      );
    } finally {
      if (previousCandidate === undefined) {
        delete process.env.ARGUS_CANDIDATE_SHA;
      } else {
        process.env.ARGUS_CANDIDATE_SHA = previousCandidate;
      }
    }
  });
});

describe("guest result and chart evidence", () => {
  test("requires typed result identities and selects the latest durable result", () => {
    const first: PersistedMessageItem = {
      id: "message-result-1",
      conversation_id: "conversation-fixture",
      role: "assistant",
      content: "redacted fixture prose",
      metadata: {
        result_run_id: "run-1",
        result_card: { evidenceArtifactId: "evidence-1" },
      },
    };
    const second: PersistedMessageItem = {
      ...first,
      id: "message-result-2",
      metadata: {
        result_run_id: "run-2",
        result_card: { evidenceArtifactId: "evidence-2" },
      },
    };

    expect(latestResultFacts([first, second])).toEqual({
      messageId: "message-result-2",
      runId: "run-2",
      evidenceId: "evidence-2",
    });
    expect(() =>
      latestResultFacts([
        {
          ...second,
          metadata: {
            result_card: {
              description: "run-2 evidence-2",
            },
          },
        },
      ]),
    ).toThrow("typed result");
  });

  test("distinguishes a changed chart viewport and exact immutable result truth", () => {
    expect(
      binaryEvidenceDiffers(
        new Uint8Array([1, 2, 3]),
        new Uint8Array([1, 2, 3]),
      ),
    ).toBe(false);
    expect(
      binaryEvidenceDiffers(
        new Uint8Array([1, 2, 3]),
        new Uint8Array([1, 4, 3]),
      ),
    ).toBe(true);
    expect(
      resultTruthStayedStable(
        { rows: 1, fingerprint: "truth-a" },
        { rows: 1, fingerprint: "truth-a" },
      ),
    ).toBe(true);
    expect(
      resultTruthStayedStable(
        { rows: 1, fingerprint: "truth-a" },
        { rows: 1, fingerprint: "truth-b" },
      ),
    ).toBe(false);
  });
});

describe("Checks 6–20 harness guards", () => {
  const source = readFileSync(
    join(import.meta.dir, "../e2e/guest-experience.spec.ts"),
    "utf-8",
  );
  const supportSource = readFileSync(
    join(import.meta.dir, "../e2e/support/guest-qa.ts"),
    "utf-8",
  );
  const checkSource = (number: number) => {
    const start =
      new RegExp(`await runStep\\(\\s*${number}\\b`).exec(source)?.index ?? -1;
    const end =
      number === 20
        ? source.indexOf("  } finally {", start)
        : (new RegExp(`await runStep\\(\\s*${number + 1}\\b`).exec(source)
            ?.index ?? -1);
    if (start < 0 || end < 0) {
      throw new Error(`Check ${number} source boundary is missing`);
    }
    return source.slice(start, end);
  };

  test("does not use hidden range details or the permanent spacer as evidence", () => {
    expect(source).not.toContain(
      'getByTestId("result-chart-visible-period")',
    );
    expect(source).not.toContain(
      '".argus-scrollbar > .space-y-8 > *"',
    );
    expect(source).toContain('toHaveAttribute("aria-pressed", "true")');
    expect(source).toContain("binaryEvidenceDiffers");
  });

  test("uses typed API and database truth for result, usage, reload, and Recents", () => {
    const check7 = checkSource(7);
    const check8 = checkSource(8);
    const check9 = checkSource(9);

    expect(check7).toContain("latestResultFacts");
    expect(check7).toContain("guest_session");
    expect(check7).toContain("graph.runs");
    expect(check8).toContain("messagesResponse");
    expect(check8).toContain("latestResultFacts");
    expect(check8).toContain("conversationGraph");
    expect(check9).toContain('goto("/chat"');
    expect(check9).toContain("if ((await rows.count()) === 0)");
    expect(check9).toContain("await recents.click()");
    expect(check9).toContain("data-conversation-id");
    expect(check9).toContain("primaryExpiry");
  });

  test("scopes Omnisearch to its overlay and typed owned result classes", () => {
    const check10 = checkSource(10);

    expect(check10).toContain("searchSurface(page)");
    expect(check10).toContain('"Preserved local QA result"');
    expect(check10).not.toContain('"Preserved local QA strategy"');
    expect(check10).toContain(
      "closeSearchSurface(page, ownerSearchSurface)",
    );
    expect(check10).toContain(
      "closeSearchSurface(claimGuestPage, foreignSearchSurface)",
    );
    expect(check10).toContain("allowedGuestItemTypes");
    expect(check10).toContain('item.type === "evidence"');
    expect(check10).toContain("item.id === claimEvidenceId");
    expect(check10).toContain(
      "item.conversation_id === claimConversation",
    );
    expect(check10).toContain("foreignSearchResponse");
    expect(check10).toContain(
      "const evidenceRow = foreignSearchSurface",
    );
    expect(check10).toContain("await expect(evidenceRow).toHaveCount(1)");
    expect(check10).toContain(
      'evidenceRow.getByText("Preserved local QA result"',
    );
    expect(check10).toContain("deniedBodyContainsNoPrivatePayload");
    expect(check10).not.toContain(
      '.getByRole("button", { name: "Close search" })',
    );
    expect(check10).not.toContain("JSON.stringify(search.body).includes");
  });

  test("binds Check 11 to a distinct persisted confirmation before clicking Run", () => {
    const check11 = checkSource(11);

    expect(check11).toContain("distinctConfirmationFacts");
    expect(check11).toContain("confirmationCards(page)");
    expect(check11).toMatch(
      /secondState\.facts\.requestedDateRange\)\.toEqual\(\s*previousFacts\.effectiveDateRange/,
    );
    expect(check11).not.toMatch(
      /secondState\.facts\.requestedDateRange\)\.toEqual\(\s*previousFacts\.requestedDateRange/,
    );
    expect(check11).not.toContain("runButtons.last()");
  });

  test("keeps decision and cancel assertions scoped to the typed result artifact", () => {
    const check12 = checkSource(12);
    const check14 = checkSource(14);

    expect(check12).toContain("resultCard(page)");
    expect(check12).toContain("primaryEvidenceId");
    expect(check14).toContain("resultCard(page)");
    expect(check14).toContain("handoffCount");
    expect(check14).toContain("snapshotStayedStable");
    expect(check14).toContain("toHaveText(draft)");
    expect(check14).not.toContain("toHaveValue(draft)");
  });

  test("preserves the approved public-mode New chat acceptance", () => {
    const check13 = checkSource(13);

    expect(check13).toContain(
      'getByRole("button", { name: "Create account" })',
    );
    expect(check13).toContain(
      'getByRole("button", { name: "Sign in to keep it" })',
    );
    expect(check13).toContain("publicHydrationResponse");
    expect(check13).toContain("resultCard(page)");
  });

  test("proves typed exactly-once conversion and complete atomic claim graphs", () => {
    const check15 = checkSource(15);
    const check16 = checkSource(16);
    const ownerGraphCounter = source.slice(
      source.indexOf("function mutableGraphRows"),
      source.indexOf("function cleanupGraphRows"),
    );

    expect(check15).toContain("same_uuid_conversion");
    expect(check15).toContain("decisionTargetsEvidence");
    expect(check15).toContain("POST /api/v1/auth/guest/link");
    expect(check16).toContain("context_packets");
    expect(check16).toContain("run_context_packets");
    expect(check16).toContain("sameGraphIds");
    expect(check16).toContain("guestClaim.pending_action");
    expect(check16).toContain("decisionTargetsEvidence");
    expect(ownerGraphCounter).not.toContain("checkpoint_blobs");
    expect(ownerGraphCounter).not.toContain("checkpoint_writes");
    expect(check16).toContain(
      "sourceAfter.checkpoints.length === before.checkpoints.length",
    );
  });

  test("proves feedback consent in both directions without storing private evidence", () => {
    const check17 = checkSource(17);

    expect(check17).toContain("uncheckedContext");
    expect(check17).toContain("approvedContext");
    expect(check17).toContain("feedbackPrivacy({");
    expect(check17).toContain("sensitive_value_rows");
    expect(check17).not.toContain("includeCleanupEvidence: true");
  });

  test("hydrates a durable retry and never fabricates recovery with request aborts", () => {
    const check18 = checkSource(18);

    expect(check18).toContain("seedDurableRetryableFailure");
    expect(check18).toContain("messagesResponse");
    expect(check18).toContain("recoveryFixture.failedAssistantId");
    expect(check18).toContain('recoveryMetadata.code === "runtime_failure"');
    expect(check18).toContain("retryable === true");
    expect(check18).not.toContain("await retry.click()");
    expect(check18).not.toContain('route.abort("connectionreset")');
    expect(check18).not.toContain("unroute");
  });

  test("uses the bounded cleanup predicate and proves complete cleanup retention", () => {
    const check19 = checkSource(19);

    expect(check19).toContain("cleanupExpectedGuestCandidates");
    expect(check19).toContain("markClaimedWorkspaceCleanupReady");
    expect(check19).toContain("claimedDestinationBefore");
    expect(check19).toContain("sameGraphIds");
    expect(check19).toContain("cleanupRetentionState");
    expect(check19).toContain("retentionBefore");
    expect(check19).toContain("retentionAfter");
    expect(check19).toContain("checkpoint_blobs");
    expect(check19).toContain("checkpoint_writes");
    expect(check19).toContain("cleanupGraphRows(expiredGraphAfter)");
    expect(check19).toContain("includeCleanupEvidence: true");
    expect(check19).toContain("retained_route_rows");
    expect(check19).toContain("retained_cost_rows");
    expect(supportSource).toContain("includeCleanupEvidence?: boolean");
  });

  test("keeps product safety failures separate from sanitized teardown evidence", () => {
    const check20 = checkSource(20);
    const teardown = source.slice(source.indexOf("  } finally {"));

    expect(check20).toContain('detail.phase === "product"');
    expect(check20).toContain("server_product_analytics_disabled");
    expect(check20).toContain("deniedBodyContainsNoPrivatePayload");
    expect(teardown).toContain('detail.phase === "teardown"');
    expect(teardown).toContain("teardown_failed_request_count");
    expect(teardown).not.toContain(
      "evidence.failed_request_count = monitors.reduce",
    );
  });
});
