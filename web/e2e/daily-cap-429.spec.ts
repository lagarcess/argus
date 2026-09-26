import { expect, test, type Page } from "@playwright/test";
import {
  COPY,
  MIDNIGHT_RETRY_AFTER,
  RAW_SERVER_DETAIL,
  VIEWPORTS,
  captureEvidence,
  installComputeLimitJourney,
  sendQuestion,
} from "./fixtures/compute-limit-journey";

test.use({ timezoneId: "America/Santo_Domingo" });

async function expectDailyCapNotice(page: Page, language: keyof typeof COPY) {
  const notice = page.getByTestId("recovery-failure-notice");
  await expect(notice).toHaveCount(1);
  await expect(notice).toBeVisible();
  await expect(notice).toHaveAttribute("role", "status");
  await expect(notice).toHaveText(COPY[language].capError);

  const message = page.locator("[data-message-id]").filter({ has: notice });
  await expect(message).toHaveCount(1);
  // Copy, ratings, and More Actions must be absent, including hover-only buttons.
  await expect(message.getByRole("button", { includeHidden: true })).toHaveCount(0);
}

for (const language of ["en", "es-419"] as const) {
  for (const viewport of VIEWPORTS) {
    for (const account of ["guest", "registered"] as const) {
      for (const header of ["midnight", "missing"] as const) {
        test(`daily cap states the local reset: ${account}, ${language}, ${viewport.name}, ${header} header`, async ({ page }) => {
          await page.setViewportSize(viewport);
          const evidence = await installComputeLimitJourney(page, {
            account, language, status: 429,
            retryAfter: header === "midnight" ? MIDNIGHT_RETRY_AFTER : undefined,
          });
          await sendQuestion(page, language);
          const copy = COPY[language];
          await expectDailyCapNotice(page, language);
          await expect(page.getByText(copy.prompt, { exact: true })).toHaveCount(1);
          await expect(page.getByText(RAW_SERVER_DETAIL, { exact: true })).toHaveCount(0);
          await expect(page.getByText(/wait a moment|espera un momento/i)).toHaveCount(0);
          await expect(page.getByRole("button", { name: copy.retrySoon })).toHaveCount(0);
          expect(evidence.streamStatuses).toEqual([429]);
          if (header === "midnight") {
            await captureEvidence(page, `${account}-429-${language}-${viewport.name}`);
          }
        });
      }
    }
  }
}

test("a new chat keeps the rejected question and its daily reset notice", async ({ page }) => {
  const evidence = await installComputeLimitJourney(page, {
    account: "registered", language: "en", status: 429,
    retryAfter: MIDNIGHT_RETRY_AFTER, newConversation: true,
  });
  await sendQuestion(page, "en", true);
  await expectDailyCapNotice(page, "en");
  await expect(page.getByText(COPY.en.prompt, { exact: true })).toHaveCount(1);
  expect(evidence.streamStatuses).toEqual([429]);
});
