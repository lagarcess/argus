import {
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";
import {
  BackendController,
  BrowserSafetyMonitor,
  CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES,
  GUEST_ACCEPTANCE_CHECKS,
  apiJson,
  assertExactLocalCandidate,
  assertFreshContext,
  assertZeroState,
  authUserExists,
  binaryEvidenceDiffers,
  cleanupExpectedGuestCandidates,
  confirmationContinuityChecks,
  conversationGraph,
  createDisposableRegisteredIdentity,
  decisionTargetsEvidence,
  deleteDisposableIdentity,
  distinctConfirmationFacts,
  emptyEvidence,
  evidenceLabel,
  expectedMutationDeltasOnly,
  feedbackPrivacy,
  freshGuest,
  handoffCount,
  handoffState,
  latestConfirmationFacts,
  latestResultFacts,
  markClaimedWorkspaceCleanupReady,
  markWorkspaceExpired,
  newSignupCredentials,
  ownerSnapshot,
  profileAccountKind,
  productFailedRequestsForCheck,
  purgeDisposableQaEvidence,
  resultTruthFingerprint,
  resultTruthStayedStable,
  resultSummaryCost,
  safeConfirmationEvidence,
  safeScreenshot,
  sameGraphIds,
  seedClaimGraphFromConversation,
  seedDurableRetryableFailure,
  strictUtcTimestampsEqual,
  waitForMe,
  workspaceFacts,
  writeEvidence,
  type ConversationGraph,
  type ConfirmationFacts,
  type GuestCheckNumber,
  type GuestMe,
  type GuestUsage,
  type OwnerSnapshot,
  type PersistedMessageItem,
  type ResultFacts,
  type SafeEvidence,
} from "./support/guest-qa";

test.describe.configure({ mode: "serial" });

type MessageList = {
  items: PersistedMessageItem[];
  next_cursor: string | null;
};

type HistoryList = {
  items: Array<{
    id: string;
    title: string;
    subtitle: string;
    conversation_id?: string | null;
    expires_at?: string | null;
  }>;
  next_cursor: string | null;
};

type SearchList = {
  items: Array<{
    type:
      | "chat"
      | "strategy"
      | "collection"
      | "run"
      | "backtest"
      | "evidence"
      | "decision"
      | "idea";
    id: string;
    title: string;
    matched_text: string;
    conversation_id?: string | null;
    preview?: Record<string, unknown> | null;
  }>;
  ledger_groups?: unknown[] | null;
  next_cursor: string | null;
};

function recordOrEmpty(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function requireConversationId(page: Page): string {
  const value = new URL(page.url()).searchParams.get("conversation") ?? "";
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  ) {
    throw new Error("The browser does not own a valid conversation route");
  }
  return value;
}

function snapshotStayedStable(
  before: OwnerSnapshot,
  after: OwnerSnapshot,
  fields: Array<keyof OwnerSnapshot>,
): boolean {
  return fields.every((field) => before[field] === after[field]);
}

function mutableGraphRows(graph: ConversationGraph): number {
  return (
    graph.conversation.length +
    graph.messages.length +
    graph.strategies.length +
    graph.jobs.length +
    graph.runs.length +
    graph.ideas.length +
    graph.idea_versions.length +
    graph.evidence.length +
    graph.decisions.length +
    graph.context_packets.length +
    graph.run_context_packets.length
  );
}

function graphIdentityDifferenceCount(
  before: ConversationGraph,
  after: ConversationGraph,
): number {
  return (Object.keys(before) as Array<keyof ConversationGraph>).reduce(
    (total, key) => {
      const beforeIds = new Set(before[key]);
      const afterIds = new Set(after[key]);
      return (
        total +
        [...beforeIds].filter((id) => !afterIds.has(id)).length +
        [...afterIds].filter((id) => !beforeIds.has(id)).length
      );
    },
    0,
  );
}

function resultCard(page: Page) {
  return page.locator(
    'section[aria-label="Hero + Delta Evidence Card"]',
  );
}

function confirmationCards(page: Page) {
  return page.locator("section:has([data-confirmation-status])");
}

function searchSurface(page: Page) {
  const searchInput = page.getByPlaceholder("Search Argus...");
  return page.locator("div.fixed.inset-0").filter({ has: searchInput }).first();
}

async function closeSearchSurface(page: Page, surface: Locator) {
  await page.keyboard.press("Escape");
  await expect(surface).toBeHidden();
}

function durableFailureMessage(page: Page) {
  const failureText = page.getByText(
    "Something went wrong. Your conversation is saved. Please try again.",
    { exact: true },
  );
  return page.locator("div.group.relative").filter({ has: failureText }).first();
}

function deniedBodyContainsNoPrivatePayload(body: unknown): boolean {
  const record = recordOrEmpty(body);
  const forbiddenKeys = [
    "items",
    "messages",
    "conversation",
    "result",
    "result_card",
  ];
  return (
    forbiddenKeys.every((key) => !Object.hasOwn(record, key)) &&
    !/Preserved local QA|Simulation Complete/i.test(JSON.stringify(record))
  );
}

function mergeMutationCounts(
  monitors: BrowserSafetyMonitor[],
): Record<string, number> {
  const merged = new Map<string, number>();
  for (const monitor of monitors) {
    for (const [route, count] of Object.entries(monitor.mutationSnapshot())) {
      merged.set(route, (merged.get(route) ?? 0) + count);
    }
  }
  return Object.fromEntries([...merged.entries()].sort());
}

function mutationTotal(counts: Record<string, number>): number {
  return Object.values(counts).reduce((sum, count) => sum + count, 0);
}

function mergeSafetyDetails(monitors: BrowserSafetyMonitor[]) {
  return monitors.flatMap((monitor) => monitor.detailSnapshot());
}

async function runStep(
  number: GuestCheckNumber,
  evidence: SafeEvidence,
  setCurrent: (number: GuestCheckNumber | null) => void,
  body: () => Promise<void>,
  recordCompletion = true,
): Promise<void> {
  const contract = GUEST_ACCEPTANCE_CHECKS[number - 1];
  setCurrent(number);
  await test.step(
    `Check ${String(number).padStart(2, "0")} — ${contract.title}`,
    body,
  );
  if (recordCompletion) evidence.completed_checks.push(number);
  setCurrent(null);
}

test("@guest-experience exact-head 20-check matrix", async ({
  browser,
  page,
}) => {
  test.slow();
  assertExactLocalCandidate();

  const backend = new BackendController();
  const evidence = emptyEvidence();
  const contexts: BrowserContext[] = [page.context()];
  const monitors: BrowserSafetyMonitor[] = [];
  const disposableUserIds = new Set<string>();
  let currentCheck: GuestCheckNumber | null = null;
  let safetyPhase: "product" | "teardown" = "product";

  let primaryMe: GuestMe | null = null;
  let primaryOwner = "";
  let primaryConversation = "";
  let primaryExpiry = "";
  let primaryGraph: ConversationGraph | null = null;
  let primaryEvidenceId = "";
  let postResultSnapshot: OwnerSnapshot | null = null;
  let initialConfirmationFacts: ConfirmationFacts | null = null;
  let latestActiveConfirmationFacts: ConfirmationFacts | null = null;
  let initialConfirmationCardCount = 0;
  let primaryResultFacts: ResultFacts | null = null;

  let claimGuestContext: BrowserContext | null = null;
  let claimGuestPage: Page | null = null;
  let claimGuestOwner = "";
  let claimConversation = "";
  let claimEvidenceId = "";

  let existingAccount:
    | Awaited<ReturnType<typeof createDisposableRegisteredIdentity>>
    | null = null;
  let feedbackGuestOwner = "";

  const attachMonitor = (target: Page) => {
    const monitor = new BrowserSafetyMonitor(() => ({
      check: currentCheck,
      phase: safetyPhase,
    }));
    monitor.attach(target);
    monitors.push(monitor);
    return monitor;
  };
  attachMonitor(page);

  try {
    await backend.start(false);

    await runStep(1, evidence, (value) => (currentCheck = value), async () => {
      await assertFreshContext(page.context());
      evidence.fresh_context_verified = true;
      primaryMe = await freshGuest(page, {
        onBootstrapOwner(owner) {
          primaryOwner = owner;
          disposableUserIds.add(owner);
        },
      });
      primaryOwner = primaryMe.user.id;
      primaryExpiry = primaryMe.guest?.expires_at ?? "";
      disposableUserIds.add(primaryOwner);
      evidence.owner_labels.push(evidenceLabel("owner", primaryOwner));

      expect(primaryMe.account_kind).toBe("guest");
      expect(primaryMe.user.email).toBeNull();
      expect(primaryMe.guest).not.toBeNull();
      expect(primaryMe.public_account_access_enabled).toBe(false);
      await expect(page.getByTestId("chat-input")).toBeVisible();
      await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
      await expect(
        page.getByRole("button", { name: /Create account/i }),
      ).toHaveCount(0);
      expect(profileAccountKind(primaryOwner)).toEqual({
        is_anonymous: true,
        email_present: false,
      });
      expect(workspaceFacts(primaryOwner)).toMatchObject({
        exists: true,
        active: true,
        fixed_seven_days: true,
      });
    });

    await runStep(2, evidence, (value) => (currentCheck = value), async () => {
      const writesBefore = mergeMutationCounts(monitors);
      const expiryBefore = ownerSnapshot(primaryOwner).expires_at;
      await expect(
        page.getByText("Test an investing idea against history."),
      ).toBeVisible();
      await expect(page.getByTestId("guest-legal-before_message")).toBeVisible();
      await expect(page.getByTestId("guest-temporary-notice")).toHaveCount(1);
      await expect(
        page.getByRole("button", { name: "Test Apple vs SPY" }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Test Bitcoin (BTC) hold" }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Test weekly Nvidia buys" }),
      ).toBeVisible();

      await page.getByRole("button", { name: "Guest settings" }).click();
      await expect(page.getByRole("menu", { name: "Guest settings" })).toBeVisible();
      await page.getByRole("menuitem", { name: "Language" }).click();
      await expect(page.getByRole("dialog", { name: "Language" })).toBeVisible();
      await page.getByRole("button", { name: /Español/ }).click();
      await expect(
        page.getByText("Prueba una idea de inversión con datos históricos."),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Ajustes de invitado" }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Iniciar sesión" }),
      ).toBeVisible();
      await expect(page.getByTestId("chat-input")).toHaveAccessibleName(
        "¿Qué quieres probar?",
      );
      await expect(
        page.getByText("¿Qué quieres probar?", { exact: true }),
      ).toBeVisible();
      await page.setViewportSize({ width: 390, height: 844 });
      await safeScreenshot(page, "02-spanish-mobile");

      await page
        .getByRole("button", { name: "Ajustes de invitado" })
        .click();
      await page.getByRole("menuitem", { name: "Idioma" }).click();
      await page.getByRole("button", { name: /English/ }).click();
      await page.setViewportSize({ width: 1440, height: 1000 });
      await expect(
        page.getByText("Test an investing idea against history."),
      ).toBeVisible();

      expect(ownerSnapshot(primaryOwner).expires_at).toBe(expiryBefore);
      const writesAfter = mergeMutationCounts(monitors);
      expect(
        (writesAfter["PATCH /api/v1/me"] ?? 0) -
          (writesBefore["PATCH /api/v1/me"] ?? 0),
      ).toBe(0);
    });

    await runStep(3, evidence, (value) => (currentCheck = value), async () => {
      const expectedMessage =
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark.";
      let ordinaryPayload = false;
      const streamRequest = page.waitForRequest((request) => {
        if (
          request.method() !== "POST" ||
          !new URL(request.url()).pathname.endsWith("/api/v1/chat/stream")
        ) {
          return false;
        }
        const payload = request.postDataJSON() as {
          message?: unknown;
          action?: unknown;
        };
        ordinaryPayload =
          payload.message === expectedMessage &&
          (payload.action === undefined || payload.action === null);
        return true;
      });
      await page.getByRole("button", { name: "Test Apple vs SPY" }).click();
      await streamRequest;
      expect(ordinaryPayload).toBe(true);
      await expect(page.getByText(expectedMessage, { exact: true })).toBeVisible();
      await expect(
        page.getByRole("button", { name: /Run backtest/i }),
      ).toBeVisible({ timeout: 180_000 });
      await expect
        .poll(() => new URL(page.url()).searchParams.has("conversation"), {
          timeout: 30_000,
        })
        .toBe(true);
      primaryConversation = requireConversationId(page);
      evidence.conversation_labels.push(
        evidenceLabel("conversation", primaryConversation),
      );
      const snapshot = ownerSnapshot(primaryOwner);
      expect(snapshot.conversations).toBe(1);
      expect(snapshot.user_messages).toBe(1);
      expect(snapshot.assistant_messages).toBeGreaterThanOrEqual(1);
      const messages = await apiJson<MessageList>(
        page.context().request,
        `/conversations/${primaryConversation}/messages?limit=100`,
      );
      expect(messages.status).toBe(200);
      initialConfirmationFacts = latestConfirmationFacts(messages.body.items);
      latestActiveConfirmationFacts = initialConfirmationFacts;
      expect(initialConfirmationFacts.assetUniverse).toEqual(["AAPL"]);
      expect(initialConfirmationFacts.benchmark).toBe("SPY");
      evidence.check4_initial_confirmation = safeConfirmationEvidence(
        initialConfirmationFacts,
      );
      initialConfirmationCardCount = await page
        .locator("section:has([data-confirmation-status])")
        .count();
      expect(initialConfirmationCardCount).toBeGreaterThan(0);
    });

    await runStep(4, evidence, (value) => (currentCheck = value), async () => {
      const updateMessage =
        "Use MSFT instead of AAPL, keeping the 12-month period and SPY benchmark.";
      await page.getByTestId("chat-input").fill(updateMessage);
      await page.getByTestId("chat-send").click();
      if (!initialConfirmationFacts) {
        throw new Error("Initial canonical confirmation facts are missing");
      }
      const initialFacts = initialConfirmationFacts;
      const refinedState: {
        facts: ConfirmationFacts | null;
        messages: PersistedMessageItem[];
      } = { facts: null, messages: [] };
      await expect
        .poll(
          async () => {
            const messages = await apiJson<MessageList>(
              page.context().request,
              `/conversations/${primaryConversation}/messages?limit=100`,
            );
            if (messages.status !== 200) return false;
            const distinct = distinctConfirmationFacts(
              messages.body.items,
              initialFacts,
            );
            if (!distinct) return false;
            refinedState.facts = distinct;
            refinedState.messages = messages.body.items;
            return true;
          },
          {
            message:
              "A new persisted confirmation must have distinct message and confirmation ids",
            timeout: 180_000,
          },
        )
        .toBe(true);
      if (!refinedState.facts) {
        throw new Error("The refined canonical confirmation was not selected");
      }
      const refinedFacts = refinedState.facts;
      latestActiveConfirmationFacts = refinedFacts;
      const checks = confirmationContinuityChecks(
        initialFacts,
        refinedFacts,
        refinedState.messages,
        updateMessage,
      );

      expect(
        checks.updateMessagePersisted,
        CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES.updateMessagePersisted,
      ).toBe(true);
      expect(
        refinedFacts.assetUniverse,
        CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES.assetUniverseExactlyMsft,
      ).toEqual(["MSFT"]);
      expect(
        refinedFacts.benchmark,
        CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES.benchmarkExactlySpy,
      ).toBe("SPY");
      expect(
        refinedFacts.requestedDateRange,
        CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES.requestedDateRangeUnchanged,
      ).toEqual(initialFacts.requestedDateRange);
      expect(
        refinedFacts.effectiveDateRange,
        CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES.effectiveDateRangeUnchanged,
      ).toEqual(initialFacts.effectiveDateRange);

      const renderedConfirmations = confirmationCards(page);
      await expect
        .poll(() => renderedConfirmations.count(), {
          message: "The refined confirmation card must render as a new card",
          timeout: 30_000,
        })
        .toBeGreaterThan(initialConfirmationCardCount);
      const refinedCard = renderedConfirmations.last();
      await expect(refinedCard.getByText("MSFT", { exact: true })).toBeVisible();
      await expect(refinedCard.getByText(/SPY/i)).toBeVisible();
      await expect(
        refinedCard.getByRole("button", { name: /Run backtest/i }),
      ).toBeVisible();
      evidence.check4_refined_confirmation =
        safeConfirmationEvidence(refinedFacts);
    });

    await runStep(5, evidence, (value) => (currentCheck = value), async () => {
      const runResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname.endsWith("/api/v1/chat/stream"),
      );
      await page.getByRole("button", { name: /Run backtest/i }).click();
      expect((await runResponse).status()).toBe(200);
      await expect(page.getByTestId("result-equity-chart")).toBeVisible({
        timeout: 240_000,
      });
      await expect(page.getByText("Quick take")).toBeVisible();
      await expect(page.getByText(/Simulation Complete/i).first()).toBeVisible();
      await expect
        .poll(() => ownerSnapshot(primaryOwner).completed_runs, {
          timeout: 60_000,
        })
        .toBe(1);

      postResultSnapshot = ownerSnapshot(primaryOwner);
      expect(postResultSnapshot.succeeded_jobs).toBe(1);
      expect(postResultSnapshot.completed_runs).toBe(1);
      expect(postResultSnapshot.simulation_units).toBe(1);
      expect(postResultSnapshot.evidence).toBeGreaterThanOrEqual(1);
      primaryGraph = conversationGraph(primaryOwner, primaryConversation);
      expect(primaryGraph.jobs).toHaveLength(1);
      expect(primaryGraph.runs).toHaveLength(1);
      expect(primaryGraph.evidence.length).toBeGreaterThanOrEqual(1);
      primaryEvidenceId = primaryGraph.evidence[0];
      evidence.artifact_labels.push(
        evidenceLabel("artifact", primaryEvidenceId),
      );
      await safeScreenshot(
        page,
        "05-completed-result-chart",
        page.getByTestId("result-equity-chart"),
      );

      await expect
        .poll(() => resultSummaryCost(primaryOwner).rows, {
          timeout: 30_000,
        })
        .toBeGreaterThanOrEqual(1);
      const resultCost = resultSummaryCost(primaryOwner);
      evidence.provider_cost_usd = resultCost.cost_usd;
      evidence.provider_latency_ms = resultCost.latency_ms;
      expect(resultCost.cost_usd).toBeGreaterThan(0);
      expect(resultCost.latency_ms).toBeGreaterThan(0);
    });

    await runStep(6, evidence, (value) => (currentCheck = value), async () => {
      const before = ownerSnapshot(primaryOwner);
      const truthBefore = resultTruthFingerprint(
        primaryOwner,
        primaryConversation,
      );
      const mutationsBefore = mergeMutationCounts(monitors);
      const card = resultCard(page);
      await expect(card).toHaveCount(1);
      const chart = card.getByTestId("result-equity-chart");
      const chartBefore = await chart.screenshot();
      const range = card.getByTestId("result-chart-range-1M");
      await expect(range).toBeVisible();
      await range.click();
      await expect(range).toHaveAttribute("aria-pressed", "true");
      await expect(
        card.getByTestId("result-chart-range-ALL"),
      ).toHaveAttribute("aria-pressed", "false");
      await expect(card.getByTestId("result-chart-reset")).toBeVisible();
      await expect
        .poll(
          async () =>
            binaryEvidenceDiffers(chartBefore, await chart.screenshot()),
          {
            message: "The selected 1M chart viewport must visibly change",
            timeout: 10_000,
          },
        )
        .toBe(true);
      await page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
          ),
      );
      const after = ownerSnapshot(primaryOwner);
      const truthAfter = resultTruthFingerprint(
        primaryOwner,
        primaryConversation,
      );
      const mutationsAfter = mergeMutationCounts(monitors);
      expect(resultTruthStayedStable(truthBefore, truthAfter)).toBe(true);
      expect(
        snapshotStayedStable(before, after, [
          "messages",
          "jobs",
          "runs",
          "ideas",
          "idea_versions",
          "evidence",
          "decisions",
          "chat_units",
          "simulation_units",
          "cost_rows",
          "provider_cost_usd",
          "provider_latency_ms",
        ]),
      ).toBe(true);
      expect(
        mutationTotal(mutationsAfter) === mutationTotal(mutationsBefore),
      ).toBe(true);
    });

    await runStep(7, evidence, (value) => (currentCheck = value), async () => {
      const usage = await apiJson<GuestUsage>(
        page.context().request,
        "/me/usage",
      );
      expect(usage.status).toBe(200);
      const messageWindow = usage.body.allowances.messages.guest_session;
      const simulationWindow = usage.body.allowances.backtests.guest_session;
      const database = ownerSnapshot(primaryOwner);
      const graph = conversationGraph(primaryOwner, primaryConversation);
      const messages = await apiJson<MessageList>(
        page.context().request,
        `/conversations/${primaryConversation}/messages?limit=100`,
      );
      const apiMessageIds = messages.body.items
        .map((item) => item.id)
        .sort();
      const databaseMessageIds = [...graph.messages].sort();
      const apiResultCount = messages.body.items.filter(
        (item) =>
          Object.keys(
            recordOrEmpty(recordOrEmpty(item.metadata).result_card),
          ).length > 0,
      ).length;
      primaryResultFacts = latestResultFacts(messages.body.items);
      expect(messageWindow.used).toBe(database.chat_units);
      expect(messageWindow.period_end).toBe(primaryExpiry);
      expect(simulationWindow.used).toBe(database.simulation_units);
      expect(simulationWindow.limit).toBe(1);
      expect(simulationWindow.remaining).toBe(0);
      expect(simulationWindow.period_end).toBe(primaryExpiry);
      expect(usage.body.allowances.backtests.available_now).toBe(false);
      expect(database.simulation_units).toBe(1);
      expect(messages.status).toBe(200);
      expect(
        apiMessageIds.length === databaseMessageIds.length &&
          apiMessageIds.every(
            (id, index) => id === databaseMessageIds[index],
          ),
      ).toBe(true);
      expect(
        apiResultCount === 1 &&
          graph.runs.length === 1 &&
          graph.evidence.length === 1 &&
          primaryResultFacts.runId === graph.runs[0] &&
          primaryResultFacts.evidenceId === graph.evidence[0],
      ).toBe(true);
      const card = resultCard(page);
      await expect(card).toHaveCount(1);
      await expect(card.getByTestId("result-equity-chart")).toBeVisible();
      await expect(card.getByText("MSFT", { exact: true })).toBeVisible();
      await expect(card.getByText(/Simulation Complete/i)).toBeVisible();
      expect(
        strictUtcTimestampsEqual(database.expires_at, primaryExpiry),
      ).toBe(true);
      await expect(page.getByTestId("guest-legal-after_message")).toBeVisible();
      await expect(page.getByTestId("guest-temporary-notice")).toHaveCount(1);
      evidence.simulation_usage_matches = true;
    });

    await runStep(8, evidence, (value) => (currentCheck = value), async () => {
      const before = ownerSnapshot(primaryOwner);
      const graphBefore = conversationGraph(primaryOwner, primaryConversation);
      if (!primaryResultFacts) {
        throw new Error("Primary typed result identity is missing");
      }
      const resultFactsBefore = primaryResultFacts;
      const messagesResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "GET" &&
          new URL(response.url()).pathname.endsWith(
            `/api/v1/conversations/${primaryConversation}/messages`,
          ),
      );
      const mePromise = waitForMe(page);
      await page.reload({ waitUntil: "domcontentloaded" });
      const reloadedMe = await mePromise;
      const hydratedMessagesResponse = await messagesResponse;
      expect(hydratedMessagesResponse.status()).toBe(200);
      const hydratedMessages =
        (await hydratedMessagesResponse.json()) as MessageList;
      const resultFactsAfter = latestResultFacts(hydratedMessages.items);
      expect(reloadedMe.user.id === primaryOwner).toBe(true);
      expect(requireConversationId(page) === primaryConversation).toBe(true);
      expect(
        resultFactsAfter.messageId === resultFactsBefore.messageId &&
          resultFactsAfter.runId === resultFactsBefore.runId &&
          resultFactsAfter.evidenceId === resultFactsBefore.evidenceId,
      ).toBe(true);
      const card = resultCard(page);
      await expect(card).toHaveCount(1);
      await expect(card.getByTestId("result-equity-chart")).toBeVisible({
        timeout: 60_000,
      });
      await expect(card.getByText("MSFT", { exact: true })).toBeVisible();
      await expect(card.getByText(/Simulation Complete/i)).toBeVisible();
      const graphAfter = conversationGraph(primaryOwner, primaryConversation);
      expect(sameGraphIds(graphBefore, graphAfter)).toBe(true);
      expect(
        snapshotStayedStable(before, ownerSnapshot(primaryOwner), [
          "messages",
          "jobs",
          "runs",
          "evidence",
          "chat_units",
          "simulation_units",
        ]),
      ).toBe(true);
    });

    await runStep(9, evidence, (value) => (currentCheck = value), async () => {
      await page.goto("/chat", { waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("chat-input")).toBeVisible();
      await expect(resultCard(page)).toHaveCount(0);
      const expand = page.getByRole("button", { name: "Expand sidebar" });
      if (await expand.isVisible()) await expand.click();
      const sidebar = page.locator("aside");
      const recents = sidebar.getByRole("button", { name: "Recents" });
      await expect(recents).toBeVisible();
      const rows = sidebar.locator("[data-conversation-id]");
      if ((await rows.count()) === 0) {
        await recents.click();
      }
      await expect(rows).toHaveCount(1);
      const row = sidebar.locator(
        `[data-conversation-id="${primaryConversation}"]`,
      );
      await expect(row).toHaveCount(1);
      const expiry = row.locator("time[datetime]");
      await expect(expiry).toHaveCount(1);
      expect((await expiry.getAttribute("datetime")) === primaryExpiry).toBe(
        true,
      );
      const history = await apiJson<HistoryList>(
        page.context().request,
        "/history?limit=20",
      );
      expect(history.status).toBe(200);
      expect(
        history.body.items.length === 1 &&
          history.body.items[0].conversation_id === primaryConversation &&
          history.body.items[0].expires_at === primaryExpiry,
      ).toBe(true);
      const rowCopy = await row
        .locator("div.min-w-0 span")
        .allTextContents();
      expect(
        rowCopy.length >= 2 &&
          rowCopy[0] === history.body.items[0].title &&
          rowCopy[1] === history.body.items[0].subtitle,
      ).toBe(true);
      await expect(
        sidebar.getByText("Sign in to keep your history", { exact: true }),
      ).toBeVisible();
      const messagesResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "GET" &&
          new URL(response.url()).pathname.endsWith(
            `/api/v1/conversations/${primaryConversation}/messages`,
          ),
      );
      await row.click();
      expect((await messagesResponse).status()).toBe(200);
      await expect
        .poll(
          () => requireConversationId(page) === primaryConversation,
          { timeout: 30_000 },
        )
        .toBe(true);
      await expect(
        resultCard(page).getByTestId("result-equity-chart"),
      ).toBeVisible();
    });

    await runStep(10, evidence, (value) => (currentCheck = value), async () => {
      claimGuestContext = await browser.newContext();
      contexts.push(claimGuestContext);
      await assertFreshContext(claimGuestContext);
      claimGuestPage = await claimGuestContext.newPage();
      attachMonitor(claimGuestPage);
      const foreignMe = await freshGuest(claimGuestPage, {
        onBootstrapOwner(owner) {
          claimGuestOwner = owner;
          disposableUserIds.add(owner);
        },
      });
      claimGuestOwner = foreignMe.user.id;
      disposableUserIds.add(claimGuestOwner);
      evidence.owner_labels.push(evidenceLabel("owner", claimGuestOwner));
      const seeded = seedClaimGraphFromConversation({
        sourceOwnerId: primaryOwner,
        sourceConversationId: primaryConversation,
        targetOwnerId: claimGuestOwner,
      });
      claimConversation = seeded.conversationId;
      claimEvidenceId = seeded.evidenceId;
      evidence.conversation_labels.push(
        evidenceLabel("conversation", claimConversation),
      );
      evidence.artifact_labels.push(
        evidenceLabel("artifact", claimEvidenceId),
      );
      await claimGuestPage.goto(
        `/chat?conversation=${claimConversation}`,
        { waitUntil: "domcontentloaded" },
      );
      await expect(claimGuestPage.getByTestId("result-equity-chart")).toBeVisible(
        { timeout: 60_000 },
      );

      const expand = page.getByRole("button", { name: "Expand sidebar" });
      if (await expand.isVisible()) await expand.click();
      await page.getByRole("button", { name: "Search" }).click();
      const ownerSearchSurface = searchSurface(page);
      await expect(ownerSearchSurface).toBeVisible();
      await expect(
        ownerSearchSurface.getByText(
          "Search is limited to this temporary conversation. Broader grounded discovery isn’t available yet.",
        ),
      ).toBeVisible();
      const evidenceQuery = "Preserved local QA result";
      const ownerSearchResponse = page.waitForResponse(
        (response) => {
          const url = new URL(response.url());
          return (
            response.request().method() === "GET" &&
            url.pathname.endsWith("/api/v1/search") &&
            url.searchParams.get("q") === evidenceQuery
          );
        },
      );
      await ownerSearchSurface
        .getByPlaceholder("Search Argus...")
        .fill(evidenceQuery);
      const ownerSearchHttpResponse = await ownerSearchResponse;
      expect(ownerSearchHttpResponse.status()).toBe(200);
      const ownerSearch = (await ownerSearchHttpResponse.json()) as SearchList;
      expect(ownerSearch.items).toHaveLength(0);
      expect(ownerSearch.ledger_groups ?? []).toHaveLength(0);
      await expect(ownerSearchSurface.getByText("No results found")).toBeVisible();
      await closeSearchSurface(page, ownerSearchSurface);

      const foreignExpand = claimGuestPage.getByRole("button", {
        name: "Expand sidebar",
      });
      if (await foreignExpand.isVisible()) await foreignExpand.click();
      await claimGuestPage.getByRole("button", { name: "Search" }).click();
      const foreignSearchSurface = searchSurface(claimGuestPage);
      const foreignSearchResponse = claimGuestPage.waitForResponse(
        (response) => {
          const url = new URL(response.url());
          return (
            response.request().method() === "GET" &&
            url.pathname.endsWith("/api/v1/search") &&
            url.searchParams.get("q") === evidenceQuery
          );
        },
      );
      await foreignSearchSurface
        .getByPlaceholder("Search Argus...")
        .fill(evidenceQuery);
      const foreignSearchHttpResponse = await foreignSearchResponse;
      expect(foreignSearchHttpResponse.status()).toBe(200);
      const foreignSearch =
        (await foreignSearchHttpResponse.json()) as SearchList;
      const evidenceRow = foreignSearchSurface
        .locator('[role="button"]')
        .filter({ hasText: evidenceQuery });
      await expect(evidenceRow).toHaveCount(1);
      await expect(
        evidenceRow.getByText("Preserved local QA result", {
          exact: true,
        }),
      ).toHaveCount(1);
      await expect(
        evidenceRow.getByText("Evidence", { exact: true }),
      ).toBeVisible();
      const foreignRead = await apiJson<Record<string, unknown>>(
        claimGuestContext.request,
        `/conversations/${primaryConversation}/messages?limit=100`,
      );
      const allowedGuestItemTypes = new Set<SearchList["items"][number]["type"]>(
        ["chat", "run", "backtest", "evidence", "decision", "idea"],
      );
      expect(foreignSearch.items).toHaveLength(1);
      const [item] = foreignSearch.items;
      expect(
        item.type === "evidence" &&
          item.id === claimEvidenceId &&
          item.conversation_id === claimConversation &&
          foreignSearch.items.every(
            (item) =>
              allowedGuestItemTypes.has(item.type) &&
              item.conversation_id === claimConversation &&
              !/(provider|model|receipt|prompt|runtime)/i.test(
                JSON.stringify(item.preview ?? {}),
              ),
          ),
      ).toBe(true);
      expect(foreignRead.status).toBe(404);
      expect(deniedBodyContainsNoPrivatePayload(foreignRead.body)).toBe(true);
      evidence.cross_owner_result_count += ownerSearch.items.length;
      await closeSearchSurface(claimGuestPage, foreignSearchSurface);
    });

    await runStep(11, evidence, (value) => (currentCheck = value), async () => {
      if (!latestActiveConfirmationFacts) {
        throw new Error("Latest confirmation identity is missing");
      }
      const previousFacts = latestActiveConfirmationFacts;
      const renderedConfirmations = confirmationCards(page);
      const previousCardCount = await renderedConfirmations.count();
      const secondIdea = `Use AAPL instead of MSFT, keeping the SPY benchmark and testing from ${previousFacts.effectiveDateRange.start} through ${previousFacts.effectiveDateRange.end}.`;
      await page.getByTestId("chat-input").fill(secondIdea);
      await page.getByTestId("chat-send").click();
      const secondState: {
        facts: ConfirmationFacts | null;
      } = { facts: null };
      await expect
        .poll(
          async () => {
            const messages = await apiJson<MessageList>(
              page.context().request,
              `/conversations/${primaryConversation}/messages?limit=100`,
            );
            if (messages.status !== 200) return false;
            const distinct = distinctConfirmationFacts(
              messages.body.items,
              previousFacts,
            );
            if (!distinct) return false;
            secondState.facts = distinct;
            return true;
          },
          {
            message:
              "The second simulation must belong to a new persisted confirmation",
            timeout: 180_000,
          },
        )
        .toBe(true);
      if (!secondState.facts) {
        throw new Error("Second simulation confirmation is missing");
      }
      latestActiveConfirmationFacts = secondState.facts;
      expect(secondState.facts.assetUniverse).toEqual(["AAPL"]);
      expect(secondState.facts.benchmark).toBe("SPY");
      expect(secondState.facts.requestedDateRange).toEqual(
        previousFacts.effectiveDateRange,
      );
      expect(secondState.facts.effectiveDateRange).toEqual(
        previousFacts.effectiveDateRange,
      );
      await expect
        .poll(() => renderedConfirmations.count(), { timeout: 30_000 })
        .toBeGreaterThan(previousCardCount);
      const secondCard = renderedConfirmations.last();
      await expect(secondCard.getByText("AAPL", { exact: true })).toBeVisible();
      await expect(secondCard.getByText(/SPY/i)).toBeVisible();
      const secondRunButton = secondCard.getByRole("button", {
        name: /Run backtest/i,
      });
      await expect(secondRunButton).toBeVisible();
      const before = ownerSnapshot(primaryOwner);
      const mutationsBefore = mergeMutationCounts(monitors);
      await secondRunButton.click();
      const dialog = page.getByRole("dialog", { name: "Sign in" });
      await expect(dialog).toBeVisible();
      await expect(
        dialog.getByText("Sign in to run another simulation."),
      ).toBeVisible();
      await expect(page.getByTestId("result-equity-chart")).toBeVisible();
      const after = ownerSnapshot(primaryOwner);
      const mutationsAfter = mergeMutationCounts(monitors);
      expect(
        snapshotStayedStable(before, after, [
          "jobs",
          "runs",
          "evidence",
          "simulation_units",
          "cost_rows",
          "provider_cost_usd",
          "provider_latency_ms",
        ]),
      ).toBe(true);
      expect(
        expectedMutationDeltasOnly(mutationsBefore, mutationsAfter, {
          "POST /api/v1/analytics/guest-events": 1,
        }),
      ).toBe(true);
      await dialog.getByRole("button", { name: "Cancel" }).last().click();
    });

    await runStep(
      12,
      evidence,
      (value) => (currentCheck = value),
      async () => {
        const before = ownerSnapshot(primaryOwner);
        const graphBefore = conversationGraph(
          primaryOwner,
          primaryConversation,
        );
        const mutationsBefore = mergeMutationCounts(monitors);
        expect(primaryResultFacts?.evidenceId === primaryEvidenceId).toBe(true);
        const card = resultCard(page);
        await card.getByRole("button", { name: "Add decision" }).click();
        const dialog = page.getByRole("dialog", { name: "Sign in" });
        await expect(dialog).toBeVisible();
        await expect(
          dialog.getByText("Sign in to save this decision."),
        ).toBeVisible();
        await dialog.getByRole("button", { name: "Cancel" }).last().click();
        await expect(card.getByTestId("result-equity-chart")).toBeVisible();
        expect(
          snapshotStayedStable(before, ownerSnapshot(primaryOwner), [
            "messages",
            "jobs",
            "runs",
            "evidence",
            "decisions",
            "chat_units",
            "simulation_units",
          ]),
        ).toBe(true);
        expect(
          sameGraphIds(
            graphBefore,
            conversationGraph(primaryOwner, primaryConversation),
          ),
        ).toBe(true);
        expect(
          expectedMutationDeltasOnly(
            mutationsBefore,
            mergeMutationCounts(monitors),
            {
              "POST /api/v1/analytics/guest-events": 1,
            },
          ),
        ).toBe(true);
      },
      false,
    );

    await runStep(13, evidence, (value) => (currentCheck = value), async () => {
      await page.getByRole("button", { name: "New chat" }).click();
      const stagedDialog = page.getByRole("dialog", {
        name: "Start a new conversation?",
      });
      await expect(stagedDialog).toBeVisible();
      await expect(
        stagedDialog.getByRole("button", { name: "Start over" }),
      ).toBeVisible();
      await expect(
        stagedDialog.getByRole("button", { name: "Sign in to keep it" }),
      ).toBeVisible();
      await expect(
        stagedDialog.getByRole("button", { name: "Create account" }),
      ).toHaveCount(0);
      await stagedDialog.getByRole("button", { name: "Cancel" }).click();

      await backend.start(true);
      const publicHydrationPromise = page.waitForResponse(
        (response) =>
          response.request().method() === "GET" &&
          new URL(response.url()).pathname.endsWith(
            `/api/v1/conversations/${primaryConversation}/messages`,
          ),
      );
      const mePromise = waitForMe(page);
      await page.reload({ waitUntil: "domcontentloaded" });
      const publicModeMe = await mePromise;
      const publicHydrationResponse = await publicHydrationPromise;
      expect(publicHydrationResponse.status()).toBe(200);
      expect(publicModeMe.user.id === primaryOwner).toBe(true);
      expect(publicModeMe.public_account_access_enabled).toBe(true);
      expect(requireConversationId(page)).toBe(primaryConversation);
      await expect(resultCard(page)).toHaveCount(1);
      await expect(
        resultCard(page).getByTestId("result-equity-chart"),
      ).toBeVisible();
      await page.getByRole("button", { name: "New chat" }).click();
      const publicDialog = page.getByRole("dialog", {
        name: "Start a new conversation?",
      });
      await expect(
        publicDialog.getByRole("button", { name: "Start over" }),
      ).toBeVisible();
      await expect(
        publicDialog.getByRole("button", { name: "Create account" }),
      ).toBeVisible();
      await expect(
        publicDialog.getByRole("button", { name: "Sign in to keep it" }),
      ).toHaveCount(0);
      await publicDialog
        .getByRole("button", { name: "Create account" })
        .click();
      const authDialog = page.getByRole("dialog", {
        name: "Create your account",
      });
      await expect(authDialog).toBeVisible();
      await authDialog.getByRole("button", { name: "Cancel" }).click();
    });

    await runStep(14, evidence, (value) => (currentCheck = value), async () => {
      const draft = "Preserve this unsent local QA draft";
      await page.getByTestId("chat-input").fill(draft);
      const before = ownerSnapshot(primaryOwner);
      const graphBefore = conversationGraph(primaryOwner, primaryConversation);
      const handoffsBefore = handoffCount(primaryOwner);
      const mutationsBefore = mergeMutationCounts(monitors);
      const card = resultCard(page);
      await card.getByRole("button", { name: "Add decision" }).click();
      const dialog = page.getByRole("dialog", { name: "Sign in" });
      await expect(dialog).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(page.getByTestId("chat-input")).toHaveText(draft);
      await expect(card.getByTestId("result-equity-chart")).toBeVisible();
      expect(requireConversationId(page) === primaryConversation).toBe(true);
      expect(handoffCount(primaryOwner)).toBe(handoffsBefore);
      expect(
        sameGraphIds(
          graphBefore,
          conversationGraph(primaryOwner, primaryConversation),
        ),
      ).toBe(true);
      expect(
        snapshotStayedStable(before, ownerSnapshot(primaryOwner), [
          "messages",
          "jobs",
          "runs",
          "decisions",
          "chat_units",
          "simulation_units",
        ]),
      ).toBe(true);
      const mutationsAfter = mergeMutationCounts(monitors);
      expect(
        expectedMutationDeltasOnly(mutationsBefore, mutationsAfter, {
          "POST /api/v1/analytics/guest-events": 1,
        }),
      ).toBe(true);
      for (const route of [
        "POST /api/v1/auth/guest/link",
        "POST /api/v1/auth/guest/handoffs",
        "POST /api/v1/auth/login",
      ]) {
        expect(
          (mutationsAfter[route] ?? 0) - (mutationsBefore[route] ?? 0),
        ).toBe(0);
      }
    });

    await runStep(15, evidence, (value) => (currentCheck = value), async () => {
      if (!primaryGraph) throw new Error("Primary result graph is missing");
      const before = conversationGraph(primaryOwner, primaryConversation);
      const beforeDecisions = ownerSnapshot(primaryOwner).decisions;
      const mutationsBefore = mergeMutationCounts(monitors);
      const signup = newSignupCredentials();
      const card = resultCard(page);
      await card.getByRole("button", { name: "Add decision" }).click();
      const loginDialog = page.getByRole("dialog", { name: "Sign in" });
      await loginDialog.getByRole("button", { name: "Sign up" }).click();
      const signupDialog = page.getByRole("dialog", {
        name: "Create your account",
      });
      await expect(signupDialog).toBeVisible();
      await safeScreenshot(page, "15-create-account-modal", signupDialog);
      await signupDialog.getByPlaceholder("Name").fill("Local QA");
      await signupDialog.getByPlaceholder("Email address").fill(signup.email);
      await signupDialog.getByPlaceholder("Password").fill(signup.password);
      const linkResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname.endsWith("/api/v1/auth/guest/link"),
      );
      await signupDialog.getByRole("button", { name: "Sign up" }).last().click();
      expect((await linkResponse).status()).toBe(200);
      disposableUserIds.add(primaryOwner);
      const mutationsAfterLink = mergeMutationCounts(monitors);
      expect(
        (mutationsAfterLink["POST /api/v1/auth/guest/link"] ?? 0) -
          (mutationsBefore["POST /api/v1/auth/guest/link"] ?? 0),
      ).toBe(1);

      await expect(
        page.getByPlaceholder("Optional note for future you"),
      ).toHaveCount(1);
      evidence.new_account_resume_count = await page
        .getByPlaceholder("Optional note for future you")
        .count();
      const account = await apiJson<GuestMe>(page.context().request, "/me");
      expect(account.status).toBe(200);
      expect(
        account.body.account_kind === "registered" &&
          account.body.user.id === primaryOwner,
      ).toBe(true);
      const profile = profileAccountKind(primaryOwner);
      expect(profile).toEqual({
        is_anonymous: false,
        email_present: true,
      });
      expect(workspaceFacts(primaryOwner).claimed_by === primaryOwner).toBe(true);
      expect(
        sameGraphIds(
          before,
          conversationGraph(primaryOwner, primaryConversation),
        ),
      ).toBe(true);
      evidence.same_uuid_conversion = true;

      await card.getByRole("button", { name: "Watching" }).click();
      await card
        .getByPlaceholder("Optional note for future you")
        .fill("Local QA decision");
      const decisionRequest = page.waitForRequest(
        (request) =>
          request.method() === "POST" &&
          new URL(request.url()).pathname.endsWith(
            `/api/v1/evidence-artifacts/${primaryEvidenceId}/decision`,
          ),
      );
      await card.getByRole("button", { name: "Save decision" }).click();
      const submittedDecision = await decisionRequest;
      const submittedDecisionBody =
        submittedDecision.postDataJSON() as Record<string, unknown>;
      expect(
        submittedDecisionBody.decision_state === "watching" &&
          new URL(submittedDecision.url()).pathname.endsWith(
            `/api/v1/evidence-artifacts/${primaryEvidenceId}/decision`,
          ),
      ).toBe(true);
      await expect
        .poll(() => ownerSnapshot(primaryOwner).decisions)
        .toBe(beforeDecisions + 1);
      expect(
        decisionTargetsEvidence({
          userId: primaryOwner,
          conversationId: primaryConversation,
          evidenceId: primaryEvidenceId,
        }),
      ).toBe(true);
      const mutationsAfterDecision = mergeMutationCounts(monitors);
      expect(
        (mutationsAfterDecision[
          "POST /api/v1/evidence-artifacts/:id/decision"
        ] ?? 0) -
          (mutationsBefore[
            "POST /api/v1/evidence-artifacts/:id/decision"
          ] ?? 0),
      ).toBe(1);
      evidence.completed_checks.push(12);
      await expect(card.getByText(/Decision: Watching/i)).toBeVisible();
      const reloadedMePromise = waitForMe(page);
      await page.reload({ waitUntil: "domcontentloaded" });
      expect((await reloadedMePromise).account_kind).toBe("registered");
      const reloadedCard = resultCard(page);
      await expect(reloadedCard.getByTestId("result-equity-chart")).toBeVisible();
      await expect(reloadedCard.getByText(/Decision: Watching/i)).toBeVisible();
      await expect(
        reloadedCard.getByPlaceholder("Optional note for future you"),
      ).toHaveCount(0);
      expect(ownerSnapshot(primaryOwner).decisions).toBe(beforeDecisions + 1);
    });

    await runStep(16, evidence, (value) => (currentCheck = value), async () => {
      if (!claimGuestContext || !claimGuestPage) {
        throw new Error("Existing-account claim guest is missing");
      }
      await backend.start(false);
      existingAccount = await createDisposableRegisteredIdentity();
      disposableUserIds.add(existingAccount.userId);
      const before = conversationGraph(claimGuestOwner, claimConversation);
      expect(
        before.conversation.length === 1 &&
          before.messages.length === 2 &&
          before.strategies.length === 1 &&
          before.jobs.length === 1 &&
          before.runs.length === 1 &&
          before.ideas.length === 1 &&
          before.idea_versions.length === 1 &&
          before.evidence.length === 2 &&
          before.decisions.length === 1 &&
          before.context_packets.length === 1 &&
          before.run_context_packets.length === 1 &&
          before.checkpoints.length === 1,
      ).toBe(true);
      const sourceUsageBefore = ownerSnapshot(claimGuestOwner);
      const mutationsBefore = mergeMutationCounts(monitors);
      await claimGuestPage.goto(
        `/chat?conversation=${claimConversation}`,
        { waitUntil: "domcontentloaded" },
      );
      await expect(claimGuestPage.getByTestId("result-equity-chart")).toBeVisible();
      const card = resultCard(claimGuestPage);
      await card.getByRole("button", { name: "Add decision" }).click();
      const modal = claimGuestPage.getByRole("dialog", { name: "Sign in" });
      await expect(modal).toBeVisible();
      await safeScreenshot(
        claimGuestPage,
        "16-existing-account-modal",
        modal,
      );
      await modal
        .getByPlaceholder("Email address")
        .fill(existingAccount.email);
      await modal.getByPlaceholder("Password").fill(existingAccount.password);
      const loginResponse = claimGuestPage.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname.endsWith("/api/v1/auth/login"),
      );
      await modal.getByRole("button", { name: "Sign In" }).click();
      const authenticatedResponse = await loginResponse;
      expect(authenticatedResponse.status()).toBe(200);
      const authenticatedBody =
        (await authenticatedResponse.json()) as Record<string, unknown>;
      const guestClaim = recordOrEmpty(authenticatedBody.guest_claim);
      const pendingAction = recordOrEmpty(guestClaim.pending_action);
      expect(
        guestClaim.conversation_id === claimConversation &&
          pendingAction.reason === "save_decision" &&
          pendingAction.conversation_id === claimConversation &&
          pendingAction.artifact_id === claimEvidenceId &&
          typeof pendingAction.action_id === "string" &&
          pendingAction.action_id !== "",
      ).toBe(true);
      await expect(
        claimGuestPage.getByPlaceholder("Optional note for future you"),
      ).toHaveCount(1);
      evidence.existing_claim_resume_count = await claimGuestPage
        .getByPlaceholder("Optional note for future you")
        .count();

      const account = await apiJson<GuestMe>(claimGuestContext.request, "/me");
      expect(
        account.status === 200 &&
          account.body.account_kind === "registered" &&
          account.body.user.id === existingAccount.userId,
      ).toBe(true);
      const after = conversationGraph(
        existingAccount.userId,
        claimConversation,
      );
      expect(sameGraphIds(before, after)).toBe(true);
      evidence.existing_claim_duplicate_count =
        graphIdentityDifferenceCount(before, after);
      expect(evidence.existing_claim_duplicate_count).toBe(0);
      const sourceAfter = conversationGraph(
        claimGuestOwner,
        claimConversation,
      );
      expect(mutableGraphRows(sourceAfter)).toBe(0);
      expect(
        sourceAfter.checkpoints.length === before.checkpoints.length &&
          sourceAfter.checkpoints.every(
            (id, index) => id === before.checkpoints[index],
          ),
      ).toBe(true);
      expect(ownerSnapshot(claimGuestOwner).chat_units).toBe(
        sourceUsageBefore.chat_units,
      );
      expect(ownerSnapshot(claimGuestOwner).simulation_units).toBe(
        sourceUsageBefore.simulation_units,
      );
      expect(ownerSnapshot(existingAccount.userId).chat_units).toBe(0);
      expect(ownerSnapshot(existingAccount.userId).simulation_units).toBe(0);
      expect(handoffState(claimGuestOwner)).toEqual({
        total: 1,
        consumed: 1,
      });
      expect(
        workspaceFacts(claimGuestOwner).claimed_by === existingAccount.userId,
      ).toBe(true);
      const mutationsAfterClaim = mergeMutationCounts(monitors);
      expect(
        (mutationsAfterClaim["POST /api/v1/auth/guest/handoffs"] ?? 0) -
          (mutationsBefore["POST /api/v1/auth/guest/handoffs"] ?? 0),
      ).toBe(1);
      expect(
        (mutationsAfterClaim["POST /api/v1/auth/login"] ?? 0) -
          (mutationsBefore["POST /api/v1/auth/login"] ?? 0),
      ).toBe(1);
      await expect(card.getByTestId("result-equity-chart")).toBeVisible();
      evidence.existing_claim_owner_changed = true;

      const destinationDecisionsBefore =
        ownerSnapshot(existingAccount.userId).decisions;
      await card.getByRole("button", { name: "Watching" }).click();
      const resumedDecisionRequest = claimGuestPage.waitForRequest(
        (request) =>
          request.method() === "POST" &&
          new URL(request.url()).pathname.endsWith(
            `/api/v1/evidence-artifacts/${claimEvidenceId}/decision`,
          ),
      );
      await card.getByRole("button", { name: "Save decision" }).click();
      const resumedDecision = await resumedDecisionRequest;
      expect(
        new URL(resumedDecision.url()).pathname.endsWith(
          `/api/v1/evidence-artifacts/${claimEvidenceId}/decision`,
        ),
      ).toBe(true);
      await expect
        .poll(() => ownerSnapshot(existingAccount!.userId).decisions)
        .toBe(destinationDecisionsBefore + 1);
      expect(
        decisionTargetsEvidence({
          userId: existingAccount.userId,
          conversationId: claimConversation,
          evidenceId: claimEvidenceId,
        }),
      ).toBe(true);
      const reloadedMePromise = waitForMe(claimGuestPage);
      await claimGuestPage.reload({ waitUntil: "domcontentloaded" });
      expect((await reloadedMePromise).user.id === existingAccount.userId).toBe(
        true,
      );
      expect(requireConversationId(claimGuestPage) === claimConversation).toBe(
        true,
      );
      const reloadedCard = resultCard(claimGuestPage);
      await expect(reloadedCard.getByTestId("result-equity-chart")).toBeVisible();
      await expect(reloadedCard.getByText(/Decision: Watching/i)).toBeVisible();
      await expect(
        reloadedCard.getByPlaceholder("Optional note for future you"),
      ).toHaveCount(0);
    });

    await runStep(17, evidence, (value) => (currentCheck = value), async () => {
      const feedbackContext = await browser.newContext();
      contexts.push(feedbackContext);
      await assertFreshContext(feedbackContext);
      const feedbackPage = await feedbackContext.newPage();
      attachMonitor(feedbackPage);
      const feedbackMe = await freshGuest(feedbackPage, {
        onBootstrapOwner(owner) {
          feedbackGuestOwner = owner;
          disposableUserIds.add(owner);
        },
      });
      feedbackGuestOwner = feedbackMe.user.id;
      disposableUserIds.add(feedbackGuestOwner);
      const seeded = seedClaimGraphFromConversation({
        sourceOwnerId: primaryOwner,
        sourceConversationId: primaryConversation,
        targetOwnerId: feedbackGuestOwner,
      });
      await feedbackPage.goto(`/chat?conversation=${seeded.conversationId}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(feedbackPage.getByTestId("result-equity-chart")).toBeVisible();
      const before = ownerSnapshot(feedbackGuestOwner);
      const openFeedback = async () => {
        await feedbackPage
          .getByRole("button", { name: "Guest settings" })
          .click();
        await feedbackPage.getByRole("menuitem", { name: "Feedback" }).click();
        const surface = feedbackPage
          .locator("div.fixed.inset-0")
          .filter({ hasText: "Provide feedback" })
          .first();
        await expect(surface.getByText("Provide feedback")).toBeVisible();
        await expect(surface.locator('input[type="email"]')).toHaveCount(0);
        return surface;
      };
      const submitFeedback = async (
        surface: Locator,
        message: string,
      ) => {
        const requestPromise = feedbackPage.waitForRequest(
          (request) =>
            request.method() === "POST" &&
            new URL(request.url()).pathname.endsWith("/api/v1/feedback"),
        );
        await surface.getByPlaceholder("What's on your mind?").fill(message);
        await surface.getByRole("button", { name: "Submit feedback" }).click();
        const request = await requestPromise;
        const payload = recordOrEmpty(request.postDataJSON());
        const context = recordOrEmpty(payload.context);
        await expect(surface.getByText("Feedback submitted.")).toBeVisible();
        await expect(surface).toBeHidden();
        return context;
      };

      const withoutContext = await openFeedback();
      const uncheckedConsent = withoutContext.getByLabel(
        "Include approved context from this conversation",
      );
      await expect(uncheckedConsent).not.toBeChecked();
      const uncheckedContext = await submitFeedback(
        withoutContext,
        "The local guest flow stayed clear.",
      );
      expect(
        uncheckedContext.surface === "guest_header" &&
          !Object.hasOwn(uncheckedContext, "conversation_id"),
      ).toBe(true);

      const withContext = await openFeedback();
      const checkedConsent = withContext.getByLabel(
        "Include approved context from this conversation",
      );
      await expect(checkedConsent).not.toBeChecked();
      await checkedConsent.check();
      await expect(checkedConsent).toBeChecked();
      await expect(
        withContext.getByText(
          "Approved conversation identifiers will be included. The transcript is not attached.",
        ),
      ).toBeVisible();
      const approvedContext = await submitFeedback(
        withContext,
        "The approved identifiers were attached safely.",
      );
      expect(
        approvedContext.surface === "guest_header" &&
          approvedContext.conversation_id === seeded.conversationId &&
          !Object.hasOwn(approvedContext, "transcript") &&
          !Object.hasOwn(approvedContext, "messages"),
      ).toBe(true);
      await expect
        .poll(() => ownerSnapshot(feedbackGuestOwner).feedback)
        .toBe(before.feedback + 2);
      const after = ownerSnapshot(feedbackGuestOwner);
      expect(after.chat_units).toBe(before.chat_units);
      expect(after.simulation_units).toBe(before.simulation_units);
      expect(after.feedback_units).toBe(before.feedback_units + 2);
      const privacy = feedbackPrivacy({
        userId: feedbackGuestOwner,
        conversationId: seeded.conversationId,
      });
      expect(privacy).toEqual({
        rows: 2,
        email_present: false,
        transcript_present: false,
        forbidden_context_fields: 0,
        unchecked_rows: 1,
        approved_context_rows: 1,
        unapproved_key_rows: 0,
        sensitive_value_rows: 0,
      });
      evidence.feedback_rows_added = after.feedback - before.feedback;
      evidence.feedback_email_present = privacy.email_present;
      evidence.feedback_transcript_present = privacy.transcript_present;
    });

    await runStep(18, evidence, (value) => (currentCheck = value), async () => {
      const feedbackContext = contexts.at(-1);
      if (!feedbackContext) throw new Error("Interrupted-turn context is missing");
      const feedbackPage = feedbackContext.pages()[0];
      const before = ownerSnapshot(feedbackGuestOwner);
      const mutationsBefore = mergeMutationCounts(monitors);
      const recoveryConversation = requireConversationId(feedbackPage);
      const recoveryFixture = seedDurableRetryableFailure({
        userId: feedbackGuestOwner,
        conversationId: recoveryConversation,
      });
      expect(recoveryFixture.inserted).toBe(true);
      const seeded = ownerSnapshot(feedbackGuestOwner);
      expect(seeded.messages).toBe(before.messages + 2);
      expect(seeded.user_messages).toBe(before.user_messages + 1);
      expect(seeded.assistant_messages).toBe(before.assistant_messages + 1);
      expect(seeded.chat_units).toBe(before.chat_units);
      expect(seeded.simulation_units).toBe(before.simulation_units);
      evidence.interrupted_usage_delta = seeded.chat_units - before.chat_units;

      const messagesResponse = feedbackPage.waitForResponse(
        (response) =>
          response.request().method() === "GET" &&
          new URL(response.url()).pathname.endsWith(
            `/api/v1/conversations/${recoveryConversation}/messages`,
          ) &&
          response.status() === 200,
      );
      await feedbackPage.reload({ waitUntil: "domcontentloaded" });
      await messagesResponse;
      await expect(
        feedbackPage.getByText(
          "Something went wrong. Your conversation is saved. Please try again.",
        ),
      ).toBeVisible();
      const failureMessage = durableFailureMessage(feedbackPage);
      await expect(failureMessage).toBeVisible();
      const retry = failureMessage.getByRole("button", {
        name: /Retry|Try again/i,
      });
      await expect(retry).toHaveCount(1);
      await expect(retry).toBeVisible();
      const durableMessages = await apiJson<MessageList>(
        feedbackContext.request,
        `/conversations/${recoveryConversation}/messages?limit=100`,
      );
      const durableAssistant = durableMessages.body.items.find(
        (item) => item.id === recoveryFixture.failedAssistantId,
      );
      const durableMetadata = recordOrEmpty(durableAssistant?.metadata);
      const recoveryMetadata = recordOrEmpty(durableMetadata.recovery);
      const retryMetadata = recordOrEmpty(durableMetadata.retry_last_turn);
      expect(
        durableMessages.status === 200 &&
          durableAssistant?.role === "assistant" &&
          durableAssistant.content ===
            "Something went wrong. Your conversation is saved. Please try again." &&
          recoveryMetadata.code === "runtime_failure" &&
          recoveryMetadata.retryable === true &&
          typeof retryMetadata.message === "string" &&
          retryMetadata.message.length > 0,
      ).toBe(true);
      const durableUsage = ownerSnapshot(feedbackGuestOwner);
      expect(durableUsage.chat_units).toBe(before.chat_units);
      expect(durableUsage.simulation_units).toBe(before.simulation_units);
      const mutationsAfter = mergeMutationCounts(monitors);
      expect(
        (mutationsAfter["POST /api/v1/chat/stream"] ?? 0) -
          (mutationsBefore["POST /api/v1/chat/stream"] ?? 0),
      ).toBe(0);
    });

    await runStep(19, evidence, (value) => (currentCheck = value), async () => {
      if (!existingAccount) throw new Error("Permanent cleanup control is missing");
      const expiryContext = await browser.newContext();
      contexts.push(expiryContext);
      await assertFreshContext(expiryContext);
      const expiryPage = await expiryContext.newPage();
      attachMonitor(expiryPage);
      let expiredOwner = "";
      const expiredMe = await freshGuest(expiryPage, {
        onBootstrapOwner(owner) {
          expiredOwner = owner;
          disposableUserIds.add(owner);
        },
      });
      expiredOwner = expiredMe.user.id;
      disposableUserIds.add(expiredOwner);
      const seeded = seedClaimGraphFromConversation({
        sourceOwnerId: primaryOwner,
        sourceConversationId: primaryConversation,
        targetOwnerId: expiredOwner,
      });
      const expiredGraph = conversationGraph(
        expiredOwner,
        seeded.conversationId,
      );
      const claimedDestinationBefore = conversationGraph(
        existingAccount.userId,
        claimConversation,
      );
      const convertedPrimaryBefore = conversationGraph(
        primaryOwner,
        primaryConversation,
      );
      const fixedExpiry = ownerSnapshot(expiredOwner).expires_at;
      await apiJson<HistoryList>(expiryContext.request, "/history?limit=20");
      expect(ownerSnapshot(expiredOwner).expires_at).toBe(fixedExpiry);
      markWorkspaceExpired(expiredOwner);
      const denied = await apiJson<{ code?: string }>(
        expiryContext.request,
        "/me",
      );
      expect(
        denied.status === 403 && denied.body.code === "guest_session_expired",
      ).toBe(true);
      markClaimedWorkspaceCleanupReady(claimGuestOwner);
      markClaimedWorkspaceCleanupReady(primaryOwner);
      const cleanup = cleanupExpectedGuestCandidates([
        expiredOwner,
        claimGuestOwner,
      ]);
      expect(cleanup).toEqual({
        dry_run_count: 2,
        deleted_count: 2,
        claimed_identity_count: 1,
        expired_workspace_count: 1,
      });
      expect(authUserExists(expiredOwner)).toBe(false);
      expect(authUserExists(claimGuestOwner)).toBe(false);
      disposableUserIds.delete(expiredOwner);
      disposableUserIds.delete(claimGuestOwner);
      expect(
        mutableGraphRows(
          conversationGraph(expiredOwner, seeded.conversationId),
        ),
      ).toBe(0);
      expect(
        conversationGraph(expiredOwner, seeded.conversationId).checkpoints,
      ).toHaveLength(0);
      expect(mutableGraphRows(expiredGraph)).toBeGreaterThan(0);
      expect(
        sameGraphIds(
          claimedDestinationBefore,
          conversationGraph(existingAccount.userId, claimConversation),
        ),
      ).toBe(true);
      expect(
        sameGraphIds(
          convertedPrimaryBefore,
          conversationGraph(primaryOwner, primaryConversation),
        ),
      ).toBe(true);
      expect(authUserExists(existingAccount.userId)).toBe(true);
      expect(authUserExists(primaryOwner)).toBe(true);
      evidence.cleanup_deleted_count = cleanup.deleted_count;
      evidence.cleanup_permanent_control_preserved = true;
    });

    await runStep(20, evidence, (value) => (currentCheck = value), async () => {
      if (!claimGuestContext || !existingAccount) {
        throw new Error("Cross-owner controls are missing");
      }
      const registeredRead = await apiJson<Record<string, unknown>>(
        page.context().request,
        `/conversations/${claimConversation}/messages?limit=100`,
      );
      const claimedRead = await apiJson<Record<string, unknown>>(
        claimGuestContext.request,
        `/conversations/${primaryConversation}/messages?limit=100`,
      );
      expect(registeredRead.status).toBe(404);
      expect(claimedRead.status).toBe(404);
      expect(deniedBodyContainsNoPrivatePayload(registeredRead.body)).toBe(true);
      expect(deniedBodyContainsNoPrivatePayload(claimedRead.body)).toBe(true);
      evidence.cross_owner_result_count +=
        Number(registeredRead.status !== 404) +
        Number(claimedRead.status !== 404);

      const productSafetyDetails = mergeSafetyDetails(monitors).filter(
        (detail) => detail.phase === "product",
      );
      const consoleErrors = productSafetyDetails.filter(
        (detail) => detail.event === "console_error",
      ).length;
      const pageErrors = productSafetyDetails.filter(
        (detail) => detail.event === "page_error",
      ).length;
      const failedRequests = productSafetyDetails.filter(
        (detail) => detail.event === "failed_request",
      ).length;
      const hostedWrites = monitors.reduce(
        (total, monitor) => total + monitor.hostedWrites,
        0,
      );
      const credentialExposure = monitors.reduce(
        (total, monitor) => total + monitor.credentialExposure,
        0,
      );
      expect(consoleErrors).toBe(0);
      expect(pageErrors).toBe(0);
      expect(failedRequests).toBe(0);
      expect(productFailedRequestsForCheck(productSafetyDetails, 18)).toEqual(
        [],
      );
      expect(hostedWrites).toBe(0);
      expect(credentialExposure).toBe(0);
      expect(evidence.cross_owner_result_count).toBe(0);
      expect(backend.flagsRestoredFalse).toBe(true);
      expect(
        [
          process.env.POSTHOG_PROJECT_TOKEN,
          process.env.POSTHOG_REGION,
          process.env.POSTHOG_HOST,
          process.env.ARGUS_POSTHOG_TIMEOUT_SECONDS,
        ].every((value) => value === undefined || value === ""),
      ).toBe(true);

      evidence.console_error_count = consoleErrors;
      evidence.page_error_count = pageErrors;
      evidence.failed_request_count = failedRequests;
      evidence.browser_safety_details = productSafetyDetails;
      evidence.hosted_write_count = hostedWrites;
      evidence.server_product_analytics_disabled = true;
      evidence.credential_exposure_count = credentialExposure;
      evidence.normalized_mutation_counts = mergeMutationCounts(monitors);
      evidence.flags_restored_false = true;
      evidence.status = "passed";
    });
  } finally {
    safetyPhase = "teardown";
    if (currentCheck !== null) evidence.failure_check = currentCheck;
    const matrixPassed = evidence.status === "passed";
    let teardownFailed = false;
    try {
      if (!backend.flagsRestoredFalse) await backend.start(false);
      evidence.flags_restored_false = backend.flagsRestoredFalse;
    } catch {
      evidence.flags_restored_false = false;
      teardownFailed = true;
    }
    try {
      await backend.stop();
    } catch {
      teardownFailed = true;
    }

    for (const context of [...contexts].reverse()) {
      try {
        await context.close();
      } catch {
        teardownFailed = true;
      }
    }
    for (const userId of disposableUserIds) {
      try {
        await deleteDisposableIdentity(userId);
      } catch {
        teardownFailed = true;
      }
    }
    try {
      purgeDisposableQaEvidence();
      assertZeroState();
    } catch {
      teardownFailed = true;
    }

    evidence.teardown_clean = !teardownFailed;
    if (teardownFailed) {
      evidence.status = "failed";
      evidence.failure_check ??= 20;
    }
    evidence.normalized_mutation_counts = mergeMutationCounts(monitors);
    const allSafetyDetails = mergeSafetyDetails(monitors);
    const teardownSafetyDetails = allSafetyDetails.filter(
      (detail) => detail.phase === "teardown",
    );
    evidence.teardown_console_error_count = teardownSafetyDetails.filter(
      (detail) => detail.event === "console_error",
    ).length;
    evidence.teardown_page_error_count = teardownSafetyDetails.filter(
      (detail) => detail.event === "page_error",
    ).length;
    evidence.teardown_failed_request_count = teardownSafetyDetails.filter(
      (detail) => detail.event === "failed_request",
    ).length;
    evidence.browser_safety_details = allSafetyDetails;
    const totalHostedWrites = monitors.reduce(
      (total, monitor) => total + monitor.hostedWrites,
      0,
    );
    const totalCredentialExposure = monitors.reduce(
      (total, monitor) => total + monitor.credentialExposure,
      0,
    );
    evidence.teardown_hosted_write_count = Math.max(
      0,
      totalHostedWrites - evidence.hosted_write_count,
    );
    evidence.teardown_credential_exposure_count = Math.max(
      0,
      totalCredentialExposure - evidence.credential_exposure_count,
    );
    writeEvidence(evidence);
    if (matrixPassed && teardownFailed) {
      throw new Error("Guest QA teardown did not restore local zero state");
    }
  }
});
