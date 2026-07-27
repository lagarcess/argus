import { expect, test } from "@playwright/test";
import {
  BackendController,
  BrowserSafetyMonitor,
  GUEST_ACCEPTANCE_CHECKS,
  apiJson,
  assertExactLocalCandidate,
  assertFreshContext,
  assertZeroState,
  cleanupRetentionState,
  conversationGraph,
  deleteDisposableIdentity,
  feedbackPrivacy,
  freshGuest,
  guestWorkspaceExpiryIsImmutable,
  LOCAL_API_BASE,
  LOCAL_APP_ORIGIN,
  markWorkspaceExpired,
  ownerSnapshot,
  purgeDisposableQaEvidence,
  seedClaimGraphFromConversation,
  seedClaimSourceResultFixture,
  seedDistinctGuestConfirmation,
  seedDurableRetryableFailure,
  seedGuestActiveConfirmationFixture,
  seedGuestSimulationExhaustionFixture,
  workspaceFacts,
  zeroStateSnapshot,
} from "./support/guest-qa";

test.describe.configure({ mode: "serial" });

test("guest QA setup and teardown are healthy without a runtime turn", async ({
  page,
}) => {
  expect(GUEST_ACCEPTANCE_CHECKS).toHaveLength(20);
  expect(GUEST_ACCEPTANCE_CHECKS.map(({ number }) => number)).toEqual(
    Array.from({ length: 20 }, (_, index) => index + 1),
  );
  expect(new Set(GUEST_ACCEPTANCE_CHECKS.map(({ title }) => title)).size).toBe(
    20,
  );
  assertExactLocalCandidate();
  assertZeroState();
  expect(
    Object.values(zeroStateSnapshot()).every(
      (value) => Number.isInteger(value) && value >= 0,
    ),
  ).toBe(true);

  const backend = new BackendController();
  const monitor = new BrowserSafetyMonitor();
  monitor.attach(page);
  let guestOwner = "";
  try {
    await backend.start(false);
    await expect
      .poll(
        async () => {
          const response = await fetch(LOCAL_APP_ORIGIN).catch(() => null);
          return response?.status ?? 0;
        },
        { timeout: 5_000, intervals: [100, 250, 500] },
      )
      .toBe(200);
    await assertFreshContext(page.context());
    const guest = await freshGuest(page, {
      onBootstrapOwner(owner) {
        guestOwner = owner;
      },
    });
    expect(guest.user.id).toBe(guestOwner);
    expect(guest.account_kind).toBe("guest");
    expect(guest.user.email).toBeNull();
    expect(guest.guest).not.toBeNull();
    await page.getByRole("button", { name: "Guest settings" }).click();
    await page.getByRole("menuitem", { name: "Language" }).click();
    await page.getByRole("button", { name: /Español/ }).click();
    await expect(page.getByTestId("chat-input")).toHaveAccessibleName(
      "¿Qué quieres probar?",
    );
    await expect(
      page.getByText("¿Qué quieres probar?", { exact: true }),
    ).toBeVisible();
    const response = await fetch(`${LOCAL_API_BASE}/auth/session`);
    expect([200, 401]).toContain(response.status);
    expect(monitor.detailSnapshot()).toEqual([]);
    expect(monitor.hostedWrites).toBe(0);
    expect(monitor.credentialExposure).toBe(0);
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
  await expect
    .poll(
      async () => {
        const response = await fetch(`${LOCAL_API_BASE}/auth/session`).catch(
          () => null,
        );
        return response === null;
      },
      { timeout: 10_000, intervals: [100, 250, 500] },
    )
    .toBe(true);
});

test("guest entry errors fail promptly without minting an identity", async ({
  page,
}) => {
  test.setTimeout(15_000);
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  try {
    await backend.start(false);
    await page.route("**/api/v1/auth/guest", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/problem+json",
        body: JSON.stringify({
          type: "about:blank",
          title: "Service Unavailable",
          status: 503,
          code: "guest_bootstrap_unavailable",
          detail: "The local guest bootstrap is unavailable.",
        }),
      });
    });
    await expect(freshGuest(page)).rejects.toThrow(
      "Guest public entry failed before authentication",
    );
    expect(zeroStateSnapshot().auth_users).toBe(0);
  } finally {
    await backend.stop();
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});

test("expiry fixture preserves the fixed window and expires the local guest", async ({
  page,
}) => {
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  let guestOwner = "";
  try {
    await backend.start(false);
    const guest = await freshGuest(page, {
      onBootstrapOwner(owner) {
        guestOwner = owner;
      },
    });
    guestOwner = guest.user.id;
    markWorkspaceExpired(guestOwner);
    expect(workspaceFacts(guestOwner).fixed_seven_days).toBe(true);
    expect(guestWorkspaceExpiryIsImmutable(guestOwner)).toBe(true);
    const denied = await apiJson<{ code?: string }>(
      page.context().request,
      "/me",
    );
    expect(denied.status).toBe(403);
    expect(denied.body.code).toBe("guest_session_expired");
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});

test("durable retry fixture hydrates without sending an interpreter turn", async ({
  page,
}) => {
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  let guestOwner = "";
  try {
    await backend.start(false);
    const guest = await freshGuest(page, {
      onBootstrapOwner(owner) {
        guestOwner = owner;
      },
    });
    guestOwner = guest.user.id;
    const created = await apiJson<{
      conversation: { id: string };
    }>(page.context().request, "/conversations", {
      method: "POST",
      data: { title: null, language: "en" },
    });
    expect(created.status).toBe(200);
    expect(
      seedDurableRetryableFailure({
        userId: guestOwner,
        conversationId: created.body.conversation.id,
      }).inserted,
    ).toBe(true);
    await page.goto(`/chat?conversation=${created.body.conversation.id}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByText(
        "Something went wrong. Your conversation is saved. Please try again.",
      ),
    ).toBeVisible();
    const failureMessage = page
      .locator("div.group.relative")
      .filter({
        has: page.getByText(
          "Something went wrong. Your conversation is saved. Please try again.",
          { exact: true },
        ),
      })
      .first();
    await expect(
      failureMessage.getByRole("button", { name: /Retry|Try again/i }),
    ).toHaveCount(1);
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});

test("second-simulation gate fixture rekeys one durable confirmation without work", async ({
  page,
}) => {
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  let guestOwner = "";
  try {
    await backend.start(false);
    const guest = await freshGuest(page, {
      onBootstrapOwner(owner) {
        guestOwner = owner;
      },
    });
    guestOwner = guest.user.id;
    const created = await apiJson<{
      conversation: { id: string };
    }>(page.context().request, "/conversations", {
      method: "POST",
      data: { title: null, language: "en" },
    });
    expect(created.status).toBe(200);
    const fixture = seedGuestSimulationExhaustionFixture({
      userId: guestOwner,
      conversationId: created.body.conversation.id,
    });
    const activeConfirmation = seedGuestActiveConfirmationFixture({
      userId: guestOwner,
      conversationId: created.body.conversation.id,
    });
    expect(activeConfirmation.confirmationId).not.toBe(fixture.confirmationId);
    const hydrationResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        response.status() === 200 &&
        new URL(response.url()).pathname.endsWith(
          `/api/v1/conversations/${created.body.conversation.id}/messages`,
        ),
    );
    await page.goto(
      `/chat?conversation=${created.body.conversation.id}`,
      { waitUntil: "domcontentloaded" },
    );
    expect((await hydrationResponse).status()).toBe(200);
    const activeCard = page.locator("section.argus-confirmation-reveal").filter({
      has: page.locator('[data-confirmation-status="ready_to_run"]'),
    });
    await expect(activeCard).toHaveCount(1);
    await expect(
      activeCard.getByText("Benchmark: SPY", { exact: true }),
    ).toBeVisible();
    const before = ownerSnapshot(guestOwner);
    const beforeGraph = conversationGraph(
      guestOwner,
      created.body.conversation.id,
    );
    const seeded = seedDistinctGuestConfirmation({
      userId: guestOwner,
      conversationId: created.body.conversation.id,
      sourceMessageId: activeConfirmation.messageId,
    });
    const after = ownerSnapshot(guestOwner);
    const afterGraph = conversationGraph(
      guestOwner,
      created.body.conversation.id,
    );
    expect(seeded.confirmationId).not.toBe(
      activeConfirmation.confirmationId,
    );
    expect(after.messages - before.messages).toBe(1);
    expect(after.assistant_messages - before.assistant_messages).toBe(1);
    expect(after.jobs).toBe(before.jobs);
    expect(after.runs).toBe(before.runs);
    expect(after.simulation_units).toBe(before.simulation_units);
    expect(after.route_receipts).toBe(before.route_receipts);
    expect(after.cost_rows).toBe(before.cost_rows);
    expect(
      afterGraph.messages.filter((id) => !beforeGraph.messages.includes(id)),
    ).toEqual([seeded.messageId]);
    for (const key of Object.keys(beforeGraph) as Array<
      keyof typeof beforeGraph
    >) {
      if (key === "messages") continue;
      expect(afterGraph[key]).toEqual(beforeGraph[key]);
    }
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});

test("complete claim graph fixture seeds and tears down without an interpreter turn", async ({
  page,
}) => {
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  const disposableOwners = new Set<string>();
  const browser = page.context().browser();
  if (!browser) throw new Error("Claim fixture preflight needs a browser");
  const targetContext = await browser.newContext();
  try {
    await backend.start(false);
    const sourceGuest = await freshGuest(page, {
      onBootstrapOwner(owner) {
        disposableOwners.add(owner);
      },
    });
    disposableOwners.add(sourceGuest.user.id);
    const sourceConversation = await apiJson<{
      conversation: { id: string };
    }>(page.context().request, "/conversations", {
      method: "POST",
      data: { title: null, language: "en" },
    });
    expect(sourceConversation.status).toBe(200);
    seedClaimSourceResultFixture({
      userId: sourceGuest.user.id,
      conversationId: sourceConversation.body.conversation.id,
    });

    await assertFreshContext(targetContext);
    const targetPage = await targetContext.newPage();
    const targetGuest = await freshGuest(targetPage, {
      onBootstrapOwner(owner) {
        disposableOwners.add(owner);
      },
    });
    disposableOwners.add(targetGuest.user.id);
    const seeded = seedClaimGraphFromConversation({
      sourceOwnerId: sourceGuest.user.id,
      sourceConversationId: sourceConversation.body.conversation.id,
      targetOwnerId: targetGuest.user.id,
      includeCleanupEvidence: true,
    });
    const graph = conversationGraph(targetGuest.user.id, seeded.conversationId);
    expect(
      graph.conversation.length === 1 &&
        graph.messages.length === 2 &&
        graph.strategies.length === 1 &&
        graph.jobs.length === 1 &&
        graph.runs.length === 1 &&
        graph.ideas.length === 1 &&
        graph.idea_versions.length === 1 &&
        graph.evidence.length === 2 &&
        graph.decisions.length === 1 &&
        graph.context_packets.length === 1 &&
        graph.run_context_packets.length === 1 &&
        graph.checkpoints.length === 1 &&
        graph.checkpoint_blobs.length === 1 &&
        graph.checkpoint_writes.length === 1,
    ).toBe(true);
    expect(
      cleanupRetentionState({
        userId: targetGuest.user.id,
        feedbackId: seeded.feedbackId,
        routeReceiptId: seeded.routeReceiptId,
        costLedgerId: seeded.costLedgerId,
      }),
    ).toEqual({
      feedback_rows: 1,
      usage_rows: 2,
      retained_route_rows: 1,
      attributed_route_rows: 1,
      retained_cost_rows: 1,
      attributed_cost_rows: 1,
      retained_cost_route_links: 1,
    });
  } finally {
    await targetContext.close();
    await backend.stop();
    for (const owner of disposableOwners) {
      await deleteDisposableIdentity(owner);
    }
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});

test("feedback evidence helper distinguishes consent without private content", async ({
  page,
}) => {
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  let guestOwner = "";
  try {
    await backend.start(false);
    const guest = await freshGuest(page, {
      onBootstrapOwner(owner) {
        guestOwner = owner;
      },
    });
    guestOwner = guest.user.id;
    const created = await apiJson<{
      conversation: { id: string };
    }>(page.context().request, "/conversations", {
      method: "POST",
      data: { title: null, language: "en" },
    });
    expect(created.status).toBe(200);
    const baseContext = {
      surface: "guest_header",
      tags: [],
      hasAttachments: false,
      attachmentCount: 0,
    };
    const unchecked = await apiJson<{ success: boolean }>(
      page.context().request,
      "/feedback",
      {
        method: "POST",
        data: {
          type: "general",
          message: "Local consent boundary feedback.",
          context: baseContext,
        },
      },
    );
    const checked = await apiJson<{ success: boolean }>(
      page.context().request,
      "/feedback",
      {
        method: "POST",
        data: {
          type: "general",
          message: "Local approved identifier feedback.",
          context: {
            ...baseContext,
            conversation_id: created.body.conversation.id,
          },
        },
      },
    );
    expect(
      unchecked.status === 200 &&
        unchecked.body.success &&
        checked.status === 200 &&
        checked.body.success,
    ).toBe(true);
    expect(
      feedbackPrivacy({
        userId: guestOwner,
        conversationId: created.body.conversation.id,
      }),
    ).toEqual({
      rows: 2,
      email_present: false,
      transcript_present: false,
      forbidden_context_fields: 0,
      unchecked_rows: 1,
      approved_context_rows: 1,
      unapproved_key_rows: 0,
      sensitive_value_rows: 0,
    });
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});

test("guest entry without a terminal signal fails within its bounded deadline", async ({
  page,
}) => {
  test.setTimeout(10_000);
  assertExactLocalCandidate();
  assertZeroState();
  await page.route(`${LOCAL_APP_ORIGIN}/`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><title>Blank local QA entry</title>",
    });
  });
  await expect(freshGuest(page, { timeoutMs: 1_000 })).rejects.toThrow(
    "Guest public entry failed before authentication",
  );
  assertZeroState();
});

test("partial anonymous bootstrap is deleted when profile verification fails", async ({
  page,
}) => {
  test.setTimeout(15_000);
  assertExactLocalCandidate();
  assertZeroState();
  const backend = new BackendController();
  let guestOwner = "";
  try {
    await backend.start(false);
    await page.route("**/api/v1/me", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/problem+json",
        body: JSON.stringify({
          type: "about:blank",
          title: "Service Unavailable",
          status: 503,
          code: "profile_verification_unavailable",
          detail: "Local profile verification is unavailable.",
        }),
      });
    });
    await expect(
      freshGuest(page, {
        timeoutMs: 5_000,
        onBootstrapOwner(owner) {
          guestOwner = owner;
        },
      }),
    ).rejects.toThrow("Guest public entry failed before authentication");
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
});
