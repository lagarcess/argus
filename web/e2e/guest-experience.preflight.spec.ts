import { expect, test } from "@playwright/test";
import {
  BackendController,
  GUEST_ACCEPTANCE_CHECKS,
  assertExactLocalCandidate,
  assertFreshContext,
  assertZeroState,
  deleteDisposableIdentity,
  freshGuest,
  purgeDisposableQaEvidence,
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
  let guestOwner = "";
  try {
    await backend.start(false);
    await expect
      .poll(
        async () => {
          const response = await fetch("http://localhost:3000").catch(
            () => null,
          );
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
    const response = await fetch(
      "http://localhost:8000/api/v1/auth/session",
    );
    expect([200, 401]).toContain(response.status);
  } finally {
    await backend.stop();
    if (guestOwner) await deleteDisposableIdentity(guestOwner);
    purgeDisposableQaEvidence();
    assertZeroState();
  }
  await expect
    .poll(
      async () => {
        const response = await fetch(
          "http://localhost:8000/api/v1/auth/session",
        ).catch(() => null);
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

test("guest entry without a terminal signal fails within its bounded deadline", async ({
  page,
}) => {
  test.setTimeout(10_000);
  assertExactLocalCandidate();
  assertZeroState();
  await page.route("http://localhost:3000/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><title>Blank local QA entry</title>",
    });
  });
  await expect(
    freshGuest(page, { timeoutMs: 1_000 }),
  ).rejects.toThrow("Guest public entry failed before authentication");
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
