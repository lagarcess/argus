import { expect, test } from "@playwright/test";
import {
  BackendController,
  GUEST_ACCEPTANCE_CHECKS,
  assertExactLocalCandidate,
  zeroStateSnapshot,
} from "./support/guest-qa";

test("guest QA setup and teardown are healthy without a runtime turn", async () => {
  expect(GUEST_ACCEPTANCE_CHECKS).toHaveLength(20);
  expect(GUEST_ACCEPTANCE_CHECKS.map(({ number }) => number)).toEqual(
    Array.from({ length: 20 }, (_, index) => index + 1),
  );
  expect(new Set(GUEST_ACCEPTANCE_CHECKS.map(({ title }) => title)).size).toBe(
    20,
  );
  assertExactLocalCandidate();
  expect(
    Object.values(zeroStateSnapshot()).every(
      (value) => Number.isInteger(value) && value >= 0,
    ),
  ).toBe(true);

  const backend = new BackendController();
  try {
    await backend.start(false);
    const response = await fetch(
      "http://localhost:8000/api/v1/auth/session",
    );
    expect([200, 401]).toContain(response.status);
  } finally {
    await backend.stop();
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
